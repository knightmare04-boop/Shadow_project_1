"""Seed the minimum viable chart of accounts, one user per RBAC role, and the
current open fiscal period. Idempotent — safe to re-run (checks existence by
natural key before inserting).

This is NOT the historical-ledger seed (that replays a research dataset's
transactions as vendors/invoices/payments — Module 5/6 territory once the
scoring engine exists to score them going in). This is just enough for the
app to boot into a usable, non-empty state.

Run:  python tools/seed_core.py
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import session_scope
from app.models import AppUser, FiscalPeriod, GLAccount
from app.models.types import FiscalPeriodStatus, UserRoleName

# A minimal but real P2P chart of accounts — enough for every posting path
# (three-way match -> AP accrual -> payment clearing) to have a home.
CHART_OF_ACCOUNTS = [
    ("1000", "Cash and Cash Equivalents", "asset"),
    ("1200", "Inventory", "asset"),
    ("1500", "Prepaid Expenses", "asset"),
    ("2000", "Accounts Payable", "liability"),
    ("2100", "Accrued Liabilities", "liability"),
    ("3000", "Retained Earnings", "equity"),
    ("5000", "Cost of Goods Sold", "expense"),
    ("6000", "Office Supplies Expense", "expense"),
    ("6100", "Professional Services Expense", "expense"),
    ("6200", "Travel & Entertainment Expense", "expense"),
    ("6300", "Utilities Expense", "expense"),
    ("6400", "Software & Subscriptions Expense", "expense"),
    ("6900", "Miscellaneous Expense", "expense"),
]

# One user per BCSE497J §4.2.1 actor. Passwords are dev-only placeholders —
# Module 4's auth service rejects these defaults outside ENV=development.
SEED_USERS = [
    ("clerk@shadow-ledger.app", "Priya Clerk", UserRoleName.erp_clerk, "devpassword123"),
    ("auditor@shadow-ledger.app", "Sam Auditor", UserRoleName.forensic_auditor, "devpassword123"),
    ("admin@shadow-ledger.app", "Alex Admin", UserRoleName.system_administrator, "devpassword123"),
]


async def seed() -> dict:
    created = {"gl_accounts": 0, "users": 0, "fiscal_periods": 0}

    async with session_scope() as db:
        for code, name, acct_type in CHART_OF_ACCOUNTS:
            existing = await db.scalar(select(GLAccount).where(GLAccount.account_code == code))
            if existing:
                continue
            db.add(GLAccount(id=uuid.uuid4(), account_code=code, name=name,
                              account_type=acct_type, is_active=True))
            created["gl_accounts"] += 1

        for email, full_name, role, plain_password in SEED_USERS:
            existing = await db.scalar(select(AppUser).where(AppUser.email == email))
            if existing:
                continue
            db.add(AppUser(
                id=uuid.uuid4(), email=email, full_name=full_name, role=role,
                hashed_password=hash_password(plain_password), is_active=True,
            ))
            created["users"] += 1

        today = date.today()
        period_code = today.strftime("%Y-%m")
        existing_period = await db.scalar(
            select(FiscalPeriod).where(FiscalPeriod.period_code == period_code)
        )
        if not existing_period:
            start = today.replace(day=1)
            end = (start.replace(month=start.month % 12 + 1, day=1)
                   if start.month < 12 else start.replace(year=start.year + 1, month=1, day=1))
            db.add(FiscalPeriod(
                id=uuid.uuid4(), period_code=period_code, start_date=start,
                end_date=end, status=FiscalPeriodStatus.open,
            ))
            created["fiscal_periods"] += 1

    return created


if __name__ == "__main__":
    result = asyncio.run(seed())
    print(f"seeded: {result}")
