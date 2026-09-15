from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import created_at_col, updated_at_col, uuid_pk


class Vendor(Base):
    """The vendor master. ``vendor_code`` is the business key auditors and
    the three-way-match/duplicate-invoice controls key off of — never the
    surrogate ``id``."""

    __tablename__ = "vendors"
    __table_args__ = (UniqueConstraint("vendor_code", name="uq_vendors_vendor_code"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    vendor_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    legal_name: Mapped[str] = mapped_column(String(256), nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(64))
    bank_account_masked: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_blocked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="Blocked by an auditor after a confirmed-fraud finding; new POs/invoices refused.",
    )

    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="vendor")
    invoices: Mapped[list["APInvoice"]] = relationship(back_populates="vendor")
