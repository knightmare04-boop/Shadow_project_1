"""Shared column types and enums for the domain model.

Money is ALWAYS ``Numeric(18, 2)`` — never ``Float``/``Double``. Floats cannot
represent currency exactly (0.1 + 0.2 != 0.3), and a fraud/audit ledger that
silently drifts by fractions of a cent is worse than one that is merely slow.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Numeric
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import TypeDecorator, CHAR
import sqlalchemy as sa

Money = Numeric(18, 2)


class GUID(TypeDecorator):
    """Portable UUID: native ``uuid`` on Postgres, CHAR(32) hex elsewhere (so
    the same models work against SQLite in unit tests without a container)."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(sa.dialects.postgresql.UUID())
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            return f"{uuid.UUID(value).hex}"
        return value.hex

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


def uuid_pk():
    return mapped_column(GUID(), primary_key=True, default=uuid.uuid4)


def created_at_col():
    return mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def updated_at_col():
    return mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(),
        onupdate=sa.func.now(), nullable=False,
    )


class PurchaseOrderStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    partially_received = "partially_received"
    fully_received = "fully_received"
    closed = "closed"
    cancelled = "cancelled"


class GoodsReceiptStatus(str, enum.Enum):
    posted = "posted"
    reversed = "reversed"


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    pending_match = "pending_match"
    matched = "matched"
    match_exception = "match_exception"
    approved = "approved"
    posted = "posted"
    paid = "paid"
    voided = "voided"


class MatchStatus(str, enum.Enum):
    not_attempted = "not_attempted"
    matched = "matched"
    price_variance = "price_variance"
    quantity_variance = "quantity_variance"
    missing_receipt = "missing_receipt"
    missing_po = "missing_po"


class PaymentRunStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    executing = "executing"
    completed = "completed"
    failed = "failed"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    posted = "posted"
    cleared = "cleared"
    failed = "failed"
    voided = "voided"


class FiscalPeriodStatus(str, enum.Enum):
    open = "open"
    closed = "closed"
    locked = "locked"        # closed + no admin override possible


class DebitCredit(str, enum.Enum):
    debit = "D"
    credit = "C"


class UserRoleName(str, enum.Enum):
    """The three actors from BCSE497J_Project_I_Report.md §4.2.1 DFD Level 0."""
    erp_clerk = "erp_clerk"
    forensic_auditor = "forensic_auditor"
    system_administrator = "system_administrator"


class ReviewFeedbackStatus(str, enum.Enum):
    """AuditAlert.feedback_status — the auditor feedback loop the demo HTML
    has no equivalent of (BCSE497J §4.2.3 domain class notes)."""
    open = "open"
    confirmed_fraud = "confirmed_fraud"
    false_positive = "false_positive"
    escalated = "escalated"
