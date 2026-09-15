"""Payment runs and payments — where the hard duplicate-payment control lives
at the schema level (defence layer 3 of 5; layers 1-2-4-5 are Module 4's
idempotency-key middleware, row lock, advisory lock, and reconciliation job).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import (
    GUID, Money, PaymentRunStatus, PaymentStatus,
    created_at_col, updated_at_col, uuid_pk,
)


class PaymentRun(Base):
    __tablename__ = "payment_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    run_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[PaymentRunStatus] = mapped_column(
        String(16), default=PaymentRunStatus.draft, nullable=False, index=True,
    )
    initiated_by_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("app_users.id"), nullable=False)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("app_users.id"))

    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    payments: Mapped[list["Payment"]] = relationship(back_populates="payment_run")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        # THE hard duplicate-payment control: an invoice can have at most one
        # non-void payment in flight or settled at any time. 'pending' is
        # deliberately included — two concurrent payment requests for the
        # same invoice cannot both reach 'pending' either, closing the race
        # the idempotency-key layer alone would still leave open if two
        # DIFFERENT idempotency keys (e.g. two different UI double-clicks
        # that generated different client-side keys) targeted the same
        # invoice. This index is what actually makes it impossible, not just
        # unlikely.
        Index(
            "uq_payments_invoice_live",
            "invoice_id",
            unique=True,
            postgresql_where="status IN ('pending', 'posted', 'cleared')",
        ),
        # Covers list_payments' invoice-scoped keyset pagination, same
        # rationale as ap_invoices' (vendor_id, id) index.
        Index("ix_payments_invoice_id_id", "invoice_id", "id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    payment_run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("payment_runs.id"), index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("ap_invoices.id"), nullable=False, index=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("vendors.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        String(16), default=PaymentStatus.pending, nullable=False, index=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), index=True)
    payment_date: Mapped[date | None]
    failure_reason: Mapped[str | None] = mapped_column(String(512))

    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    payment_run: Mapped["PaymentRun | None"] = relationship(back_populates="payments")
    invoice: Mapped["APInvoice"] = relationship(back_populates="payments")
