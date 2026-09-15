"""Payment posting — the duplicate-payment control, defence in depth.

Five independent layers, each closing a different race:
  1. Idempotency-Key middleware (app/core/idempotency_middleware.py) — the
     SAME request retried (network blip, client double-submit with the same
     key) replays the original response, never re-executes.
  2. SELECT ... FOR UPDATE on the invoice row, taken FIRST, before any
     existence check — makes the "does this invoice already have a live
     payment" check safe from a check-then-act race even when two DIFFERENT
     idempotency keys target the same invoice concurrently (two independent
     UI actions, not a retry).
  3. The partial unique index `uq_payments_invoice_live` (Module 3) — the
     database-level backstop if 1+2 are ever bypassed (a bug, a script that
     writes directly, a future code path that forgets to lock).
  4. `pg_advisory_xact_lock` per vendor around payment-RUN execution
     (execute_payment_run) — serializes an entire vendor's batch of payments
     across concurrent runs, not just one invoice at a time.
  5. `tools/reconcile_payments.py` — a periodic sweep that finds any invoice
     with more than one non-void payment and raises it as an incident. This
     is the "we were wrong somewhere" tripwire, not a preventive control.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, DuplicatePaymentError, NotFoundError
from app.core.logging import get_logger
from app.core.metrics import DUPLICATE_PAYMENT_ATTEMPTS
from app.models.audit import AuditAlert, AuditLog
from app.models.invoice import APInvoice
from app.models.payment import Payment, PaymentRun
from app.models.types import InvoiceStatus, PaymentRunStatus, PaymentStatus, ReviewFeedbackStatus
from app.models.user import AppUser
from app.services.scoring_registry import get_service

# The dataset whose "online" bundle scores live ERP payments — synth_erp is
# the domain match (its tx_type vocabulary literally includes
# "vendor_payment"). See app/services/scoring_registry.py's _CATEGORICAL_VOCAB.
LIVE_SCORING_DATASET = "synth_erp"
TREASURY_ACCOUNT_ID = "TREASURY"

log = get_logger(__name__)

_ACTIVE_PAYMENT_STATUSES = (PaymentStatus.pending, PaymentStatus.posted, PaymentStatus.cleared)


async def create_payment(
    db: AsyncSession, *, invoice_id: uuid.UUID, amount: Decimal, payment_date: date,
    actor: AppUser, payment_run_id: uuid.UUID | None = None,
) -> Payment:
    # --- Layer 2: lock the invoice row before checking anything else. ---
    invoice = await db.scalar(
        select(APInvoice).where(APInvoice.id == invoice_id).with_for_update()
    )
    if invoice is None:
        raise NotFoundError(f"invoice {invoice_id} not found")
    if invoice.status == InvoiceStatus.voided:
        raise ConflictError(f"cannot pay voided invoice {invoice_id}", error_code="invoice_voided")

    # Now safe: no other transaction can be mid-flight on this same invoice —
    # they are blocked on the row lock above until we commit or roll back.
    existing = await db.scalar(
        select(Payment).where(
            Payment.invoice_id == invoice_id,
            Payment.status.in_(_ACTIVE_PAYMENT_STATUSES),
        )
    )
    if existing is not None:
        DUPLICATE_PAYMENT_ATTEMPTS.inc()
        raise DuplicatePaymentError(
            f"invoice {invoice_id} already has an active payment ({existing.id}, status={existing.status})",
        )

    payment = Payment(
        id=uuid.uuid4(), invoice_id=invoice_id, vendor_id=invoice.vendor_id,
        amount=amount, payment_date=payment_date, status=PaymentStatus.pending,
        payment_run_id=payment_run_id,
    )
    db.add(payment)
    try:
        # --- Layer 3: force the partial unique index to be checked NOW,
        # inside this function, so we can translate it cleanly rather than
        # let a raw IntegrityError escape to the caller. Should be
        # unreachable given layer 2's lock — if it ever fires, that itself
        # is a signal the locking discipline was violated somewhere. ---
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        log.error("duplicate_payment_index_violation", invoice_id=str(invoice_id), error=str(exc))
        DUPLICATE_PAYMENT_ATTEMPTS.inc()
        raise DuplicatePaymentError(
            f"invoice {invoice_id} already has an active payment (caught at the database layer)",
        ) from exc

    invoice.status = InvoiceStatus.paid
    db.add(AuditLog(
        actor_user_id=actor.id, action="payment.create", entity_type="payment",
        entity_id=payment.id, detail={
            "invoice_id": str(invoice_id), "amount": str(amount), "payment_run_id": str(payment_run_id or ""),
        },
    ))

    await _score_payment_live(db, payment=payment, payment_date=payment_date)
    return payment


async def _score_payment_live(db: AsyncSession, *, payment: Payment, payment_date: date) -> None:
    """Fraud-score the payment through the live pipeline (Module 5) and
    persist an AuditAlert if it crosses threshold. Never blocks or fails the
    payment itself — a scoring outage degrades to "no alert produced", not
    "postings stop working" (hardening item #4, handle failed requests)."""
    service = get_service(LIVE_SCORING_DATASET)
    if service is None:
        log.warning("live_scoring_unavailable", dataset=LIVE_SCORING_DATASET,
                   payment_id=str(payment.id))
        return

    try:
        import time as _time
        ts_epoch = int(_time.mktime(payment_date.timetuple()))
        result = service.score(
            transaction_id=str(payment.id), ts=ts_epoch,
            source_account=TREASURY_ACCOUNT_ID, dest_account=str(payment.vendor_id),
            amount=float(payment.amount), categoricals={"tx_type": "vendor_payment"},
        )
    except Exception as exc:  # noqa: BLE001 — scoring must never break posting
        log.error("live_scoring_failed", payment_id=str(payment.id), error=str(exc))
        return

    log.info("payment_scored", payment_id=str(payment.id), score=result.score,
             alert=result.alert, latency_ms=result.latency_ms)

    if result.alert:
        db.add(AuditAlert(
            id=uuid.uuid4(), dataset=LIVE_SCORING_DATASET, transaction_id=str(payment.id),
            payment_id=payment.id, score=result.score, threshold=result.threshold,
            risk_drivers=result.risk_drivers, graph_evidence={},
            model_artifact=f"{LIVE_SCORING_DATASET}/online",
            feedback_status=ReviewFeedbackStatus.open,
        ))


async def execute_payment_run(db: AsyncSession, *, payment_run: PaymentRun, actor: AppUser) -> list[Payment]:
    """Executes every pending payment in a run, one vendor at a time, each
    vendor's batch serialized by an advisory lock (layer 4) so two payment
    runs that happen to overlap on the same vendor can't interleave."""
    payments: list[Payment] = []
    vendor_ids = {p.vendor_id for p in payment_run.payments}

    for vendor_id in vendor_ids:
        # Advisory locks take a bigint; hash the UUID down deterministically.
        lock_key = int.from_bytes(vendor_id.bytes[:8], "big", signed=True)
        await db.execute(select(func.pg_advisory_xact_lock(lock_key)))

        vendor_payments = [p for p in payment_run.payments if p.vendor_id == vendor_id]
        for payment in vendor_payments:
            if payment.status != PaymentStatus.pending:
                continue
            try:
                payment.status = PaymentStatus.posted
                payments.append(payment)
            except Exception as exc:  # noqa: BLE001 — record and continue the batch
                payment.status = PaymentStatus.failed
                payment.failure_reason = str(exc)[:512]
                log.error("payment_run_item_failed", payment_id=str(payment.id), error=str(exc))

    payment_run.status = PaymentRunStatus.completed
    db.add(AuditLog(
        actor_user_id=actor.id, action="payment_run.execute", entity_type="payment_run",
        entity_id=payment_run.id, detail={"n_payments": len(payments)},
    ))
    return payments
