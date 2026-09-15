"""General ledger: chart of accounts, journal entries/lines, fiscal periods.

The double-entry invariant (sum(debit) == sum(credit) per journal entry) is
NOT enforced in Python — it is enforced by a Postgres deferred constraint
trigger (see alembic/versions/<...>_gl_invariants.py) so it holds even if a
future code path forgets to check it, and so it is checked once at
transaction COMMIT (after all lines of an entry are inserted) rather than
line-by-line, which would reject every entry with more than one line.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import (
    FiscalPeriodStatus, GUID, Money,
    created_at_col, uuid_pk,
)


class GLAccount(Base):
    __tablename__ = "gl_accounts"
    __table_args__ = (UniqueConstraint("account_code", name="uq_gl_accounts_account_code"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    account_code: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    account_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="asset | liability | equity | revenue | expense",
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class FiscalPeriod(Base):
    """Period-close control: postings to a non-open period are rejected. Both
    an application-level check (fast, friendly error) and a database-level
    trigger (see the same GL-invariants migration) enforce this — the
    trigger is the one that actually matters for correctness."""

    __tablename__ = "fiscal_periods"
    __table_args__ = (UniqueConstraint("period_code", name="uq_fiscal_periods_period_code"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    period_code: Mapped[str] = mapped_column(String(8), nullable=False, comment="e.g. '2026-09'")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[FiscalPeriodStatus] = mapped_column(
        String(16), default=FiscalPeriodStatus.open, nullable=False, index=True,
    )
    closed_by_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("app_users.id"))
    # See app/models/audit.py's feedback_at comment — same fix, same bug class.
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[uuid.UUID] = uuid_pk()
    entry_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    fiscal_period_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("fiscal_periods.id"), nullable=False, index=True,
    )
    posting_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    memo: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="ap_invoice | payment | manual | goods_receipt",
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    posted_by_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("app_users.id"), nullable=False)

    created_at: Mapped[datetime] = created_at_col()

    fiscal_period: Mapped["FiscalPeriod"] = relationship()
    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="journal_entry", cascade="all, delete-orphan",
    )


class JournalLine(Base):
    __tablename__ = "journal_lines"
    __table_args__ = (
        # A line is a debit XOR a credit, never both, never neither. The
        # cross-line balance (sum debit == sum credit per entry) is the
        # trigger's job, not a single-row CHECK constraint's.
        CheckConstraint(
            "(debit_amount > 0 AND credit_amount = 0) OR "
            "(credit_amount > 0 AND debit_amount = 0)",
            name="debit_xor_credit",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    journal_entry_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("journal_entries.id"), nullable=False, index=True,
    )
    gl_account_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("gl_accounts.id"), nullable=False, index=True)
    debit_amount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    credit_amount: Mapped[Decimal] = mapped_column(Money, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(String(512))

    journal_entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
    gl_account: Mapped["GLAccount"] = relationship()
