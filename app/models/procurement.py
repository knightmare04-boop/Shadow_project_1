"""Purchase orders and goods receipts — the first two legs of the three-way
match (PO <-> goods receipt <-> invoice)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import (
    GUID, GoodsReceiptStatus, Money, PurchaseOrderStatus,
    created_at_col, updated_at_col, uuid_pk,
)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = uuid_pk()
    po_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("vendors.id"), nullable=False, index=True)
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        String(32), default=PurchaseOrderStatus.draft, nullable=False, index=True,
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    requested_by_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("app_users.id"), nullable=False)
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("app_users.id"))
    # Tolerance for the three-way match, overridable per PO; falls back to the
    # tenant-wide default (see app.services.matching) when null.
    price_tolerance_pct: Mapped[float | None]
    qty_tolerance_pct: Mapped[float | None]

    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    vendor: Mapped["Vendor"] = relationship(back_populates="purchase_orders")
    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan", order_by="PurchaseOrderLine.line_no",
    )


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[uuid.UUID] = uuid_pk()
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("purchase_orders.id"), nullable=False, index=True,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(512), nullable=False)
    quantity_ordered: Mapped[float] = mapped_column(nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Money, nullable=False)
    gl_account_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("gl_accounts.id"), nullable=False)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="lines")
    receipt_lines: Mapped[list["GoodsReceiptLine"]] = relationship(back_populates="po_line")
    invoice_lines: Mapped[list["APInvoiceLine"]] = relationship(back_populates="po_line")

    @property
    def line_total(self) -> Decimal:
        return Decimal(str(self.quantity_ordered)) * self.unit_price


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"

    id: Mapped[uuid.UUID] = uuid_pk()
    receipt_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("purchase_orders.id"), nullable=False, index=True,
    )
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    received_by_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("app_users.id"), nullable=False)
    status: Mapped[GoodsReceiptStatus] = mapped_column(
        String(16), default=GoodsReceiptStatus.posted, nullable=False,
    )

    created_at: Mapped[datetime] = created_at_col()

    purchase_order: Mapped["PurchaseOrder"] = relationship()
    lines: Mapped[list["GoodsReceiptLine"]] = relationship(
        back_populates="goods_receipt", cascade="all, delete-orphan",
    )


class GoodsReceiptLine(Base):
    __tablename__ = "goods_receipt_lines"

    id: Mapped[uuid.UUID] = uuid_pk()
    goods_receipt_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("goods_receipts.id"), nullable=False, index=True,
    )
    po_line_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("purchase_order_lines.id"), nullable=False, index=True,
    )
    quantity_received: Mapped[float] = mapped_column(nullable=False)

    goods_receipt: Mapped["GoodsReceipt"] = relationship(back_populates="lines")
    po_line: Mapped["PurchaseOrderLine"] = relationship(back_populates="receipt_lines")
