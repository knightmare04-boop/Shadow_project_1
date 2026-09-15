"""Invoice submission — runs the near-duplicate signal (Module 3's hard
unique-index block on exact (vendor_id, invoice_number) collisions happens
automatically at INSERT; this adds the soft near-duplicate review flag)."""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, DuplicateSubmissionError
from app.core.logging import get_logger
from app.models.audit import AuditLog
from app.models.invoice import APInvoice, APInvoiceLine, DuplicateCheckStatus
from app.models.procurement import PurchaseOrder
from app.models.types import InvoiceStatus, MatchStatus
from app.models.user import AppUser
from app.schemas.invoice import InvoiceCreate
from app.services.duplicate_detection import find_near_duplicates
from app.services.matching_service import match_invoice

log = get_logger(__name__)


async def create_invoice(db: AsyncSession, *, payload: InvoiceCreate, actor: AppUser) -> APInvoice:
    # quantity is float (physical unit counts can be fractional — weight,
    # hours), unit_price is Decimal (money). Python does not auto-coerce
    # float*Decimal (raises TypeError), so quantity is explicitly cast via
    # str() first — never float(Decimal), which would reintroduce binary
    # floating-point error into a money computation.
    total = sum(
        (Decimal(str(line.quantity)) * line.unit_price for line in payload.lines),
        start=Decimal("0"),
    )

    near_dupes = await find_near_duplicates(
        db, vendor_id=payload.vendor_id, invoice_number=payload.invoice_number,
        total_amount=total, invoice_date=payload.invoice_date,
    )
    dup_status = DuplicateCheckStatus.flagged_near_duplicate if near_dupes else DuplicateCheckStatus.clear

    invoice = APInvoice(
        id=uuid.uuid4(),
        invoice_number=payload.invoice_number,
        vendor_id=payload.vendor_id,
        purchase_order_id=payload.purchase_order_id,
        invoice_date=payload.invoice_date,
        due_date=payload.due_date,
        total_amount=total,
        status=InvoiceStatus.pending_match if payload.purchase_order_id else InvoiceStatus.draft,
        duplicate_check_status=dup_status,
        submitted_by_id=actor.id,
    )
    invoice.lines = [
        APInvoiceLine(
            id=uuid.uuid4(), line_no=line.line_no, po_line_id=line.po_line_id,
            description=line.description, quantity=line.quantity,
            unit_price=line.unit_price, gl_account_id=line.gl_account_id,
        )
        for line in payload.lines
    ]
    db.add(invoice)

    try:
        # The hard control: the DB-level partial unique index on
        # (vendor_id, invoice_number) for non-voided invoices.
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            f"vendor {payload.vendor_id} already has a live invoice numbered {payload.invoice_number!r}",
            error_code="duplicate_invoice_number",
        ) from exc

    db.add(AuditLog(
        actor_user_id=actor.id, action="invoice.create", entity_type="ap_invoice",
        entity_id=invoice.id, detail={
            "invoice_number": payload.invoice_number, "total_amount": str(total),
            "near_duplicates_found": len(near_dupes),
        },
    ))
    if near_dupes:
        log.warning("invoice_near_duplicate_flagged", invoice_id=str(invoice.id),
                    candidates=[str(d["candidate_invoice_id"]) for d in near_dupes])

    if payload.purchase_order_id is not None:
        po = await db.get(PurchaseOrder, payload.purchase_order_id)
        result = await match_invoice(
            db, invoice_id=invoice.id,
            po_price_tolerance_pct=po.price_tolerance_pct if po else None,
            po_qty_tolerance_pct=po.qty_tolerance_pct if po else None,
        )
        invoice.match_status = MatchStatus(result["overall_status"])
        invoice.status = (
            InvoiceStatus.pending_match if invoice.match_status != MatchStatus.matched
            else InvoiceStatus.matched
        )
        db.add(AuditLog(
            actor_user_id=actor.id, action="invoice.three_way_match", entity_type="ap_invoice",
            entity_id=invoice.id, detail=result,
        ))
        log.info("invoice_matched", invoice_id=str(invoice.id), status=result["overall_status"])

    return invoice
