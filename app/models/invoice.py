"""AP invoices — the third leg of the three-way match, and where the
duplicate-invoice control lives.

Duplicate-invoice defence in depth (mirrors the duplicate-payment design in
app/models/payment.py):
  1. A partial UNIQUE index on (vendor_id, invoice_number) for every
     non-voided invoice — the hard block. A vendor cannot have two live
     invoices with the same invoice_number, ever, at the database level.
  2. A softer near-duplicate SIGNAL (same vendor, amount within epsilon,
     invoice_date within N days) is a query-time check in
     app.services.duplicate_detection (Module 4) using pg_trgm — it raises a
     review flag (``duplicate_check_status``), it does not block, because
     legitimate recurring invoices (rent, retainers) look exactly like this.
"""
from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import (
    GUID, InvoiceStatus, MatchStatus, Money,
    created_at_col, updated_at_col, uuid_pk,
)


class DuplicateCheckStatus(str, enum.Enum):
    clear = "clear"
    flagged_near_duplicate = "flagged_near_duplicate"
    reviewed_cleared = "reviewed_cleared"
    reviewed_confirmed_duplicate = "reviewed_confirmed_duplicate"


class APInvoice(Base):
    __tablename__ = "ap_invoices"
    __table_args__ = (
        # The hard duplicate-invoice-number control. Postgres partial unique
        # index: only non-voided invoices participate, so voiding an invoice
        # and re-entering it under the same number is allowed.
        Index(
            "uq_ap_invoices_vendor_invoice_number_live",
            "vendor_id", "invoice_number",
            unique=True,
            postgresql_where="status != 'voided'",
        ),
        # Covers list_invoices' vendor-scoped keyset pagination (vendor_id
        # filter + id-ordered cursor) without a separate sort step.
        Index("ix_ap_invoices_vendor_id_id", "vendor_id", "id"),
        # Covers the status-filtered, date-ordered listing pattern (e.g.
        # "paid invoices, newest first") — measured via EXPLAIN ANALYZE at
        # 40k rows: without this, Postgres bitmap-scans every matching row
        # (23,929 of them) and sorts them all just to return 50
        # (Module 7 before/after: docs/BUILD_SPEC.md).
        Index("ix_ap_invoices_status_invoice_date", "status", "invoice_date"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("vendors.id"), nullable=False, index=True)
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("purchase_orders.id"))
    invoice_date: Mapped[date] = mapped_column(nullable=False)
    due_date: Mapped[date | None]
    total_amount: Mapped[Decimal] = mapped_column(Money, nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        String(32), default=InvoiceStatus.draft, nullable=False, index=True,
    )
    match_status: Mapped[MatchStatus] = mapped_column(
        String(32), default=MatchStatus.not_attempted, nullable=False,
    )
    duplicate_check_status: Mapped[DuplicateCheckStatus] = mapped_column(
        String(32), default=DuplicateCheckStatus.clear, nullable=False, index=True,
    )
    duplicate_of_invoice_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("ap_invoices.id"))
    submitted_by_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("app_users.id"), nullable=False)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("app_users.id"))
    fiscal_period_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("fiscal_periods.id"))

    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    vendor: Mapped["Vendor"] = relationship(back_populates="invoices")
    purchase_order: Mapped["PurchaseOrder | None"] = relationship()
    lines: Mapped[list["APInvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="APInvoiceLine.line_no",
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="invoice")


class APInvoiceLine(Base):
    __tablename__ = "ap_invoice_lines"

    id: Mapped[uuid.UUID] = uuid_pk()
    invoice_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("ap_invoices.id"), nullable=False, index=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    po_line_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("purchase_order_lines.id"))
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    quantity: Mapped[float] = mapped_column(nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    gl_account_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("gl_accounts.id"), nullable=False)

    invoice: Mapped["APInvoice"] = relationship(back_populates="lines")
    po_line: Mapped["PurchaseOrderLine | None"] = relationship(back_populates="invoice_lines")

    @property
    def line_total(self) -> Decimal:
        return Decimal(str(self.quantity)) * self.unit_price
