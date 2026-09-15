"""ORM entities — the Procure-to-Pay + GL domain model (Module 3).

Import every model module here so `from app.models import *` (used by
alembic/env.py for autogenerate) registers all tables on Base.metadata.
Import order matters only for human readability — SQLAlchemy resolves
string-based relationship() targets lazily via the shared registry.
"""
from app.models.vendor import Vendor
from app.models.procurement import (
    PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine,
)
from app.models.gl import GLAccount, FiscalPeriod, JournalEntry, JournalLine
from app.models.invoice import APInvoice, APInvoiceLine, DuplicateCheckStatus
from app.models.payment import PaymentRun, Payment
from app.models.user import AppUser
from app.models.audit import AuditLog, AuditAlert

__all__ = [
    "Vendor",
    "PurchaseOrder", "PurchaseOrderLine", "GoodsReceipt", "GoodsReceiptLine",
    "GLAccount", "FiscalPeriod", "JournalEntry", "JournalLine",
    "APInvoice", "APInvoiceLine", "DuplicateCheckStatus",
    "PaymentRun", "Payment",
    "AppUser",
    "AuditLog", "AuditAlert",
]
