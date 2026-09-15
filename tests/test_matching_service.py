"""Three-way match correctness: clean match, price variance, missing
receipt. Runs against the real dev Postgres via app.db.session (not an
isolated test DB) and rolls back at the end — a pragmatic choice for this
stage; Module 9 formalizes an isolated testcontainers-based suite for CI.
Requires the Module 1 infra stack running (docker compose up postgres) and
at least one seeded AppUser + GLAccount (tools/seed_core.py).
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

pytestmark = pytest.mark.asyncio


async def _get_fixture_ids(db):
    from app.models import AppUser, GLAccount
    user = (await db.execute(select(AppUser).limit(1))).scalar_one_or_none()
    gl = (await db.execute(select(GLAccount).limit(1))).scalar_one_or_none()
    if user is None or gl is None:
        pytest.skip("requires seeded AppUser + GLAccount (run tools/seed_core.py)")
    return user, gl


async def test_three_way_match_scenarios():
    from app.db.session import session_scope
    from app.models import PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine, Vendor
    from app.models.invoice import APInvoice, APInvoiceLine
    from app.models.types import PurchaseOrderStatus
    from app.services.matching_service import match_invoice

    async with session_scope() as db:
        user, gl = await _get_fixture_ids(db)

        vendor = Vendor(id=uuid.uuid4(), vendor_code=f"MATCH-{uuid.uuid4().hex[:8]}", legal_name="Match Test Co")
        db.add(vendor)
        await db.flush()

        po = PurchaseOrder(id=uuid.uuid4(), po_number=f"PO-{uuid.uuid4().hex[:8]}", vendor_id=vendor.id,
                           status=PurchaseOrderStatus.approved, order_date=date.today(), requested_by_id=user.id)
        db.add(po)
        await db.flush()

        po_line = PurchaseOrderLine(id=uuid.uuid4(), purchase_order_id=po.id, line_no=1,
                                    description="Widgets", quantity_ordered=100,
                                    unit_price=Decimal("10.00"), gl_account_id=gl.id)
        po_line2 = PurchaseOrderLine(id=uuid.uuid4(), purchase_order_id=po.id, line_no=2,
                                     description="Gadgets (never received)", quantity_ordered=50,
                                     unit_price=Decimal("20.00"), gl_account_id=gl.id)
        db.add_all([po_line, po_line2])
        await db.flush()

        gr = GoodsReceipt(id=uuid.uuid4(), receipt_number=f"GR-{uuid.uuid4().hex[:8]}",
                          purchase_order_id=po.id, received_date=date.today(), received_by_id=user.id)
        db.add(gr)
        await db.flush()
        db.add(GoodsReceiptLine(id=uuid.uuid4(), goods_receipt_id=gr.id, po_line_id=po_line.id, quantity_received=100))
        await db.flush()

        # Case 1: clean match
        inv1 = APInvoice(id=uuid.uuid4(), invoice_number="INV-CLEAN", vendor_id=vendor.id,
                         purchase_order_id=po.id, invoice_date=date.today(),
                         total_amount=Decimal("1000.00"), submitted_by_id=user.id)
        db.add(inv1)
        await db.flush()
        db.add(APInvoiceLine(id=uuid.uuid4(), invoice_id=inv1.id, line_no=1, po_line_id=po_line.id,
                             description="Widgets", quantity=100, unit_price=Decimal("10.00"), gl_account_id=gl.id))
        await db.flush()
        r1 = await match_invoice(db, invoice_id=inv1.id)
        assert r1["overall_status"] == "matched"

        # Case 2: price variance (PO=$10, invoiced=$15 -> 50% over tolerance)
        inv2 = APInvoice(id=uuid.uuid4(), invoice_number="INV-PRICEVAR", vendor_id=vendor.id,
                         purchase_order_id=po.id, invoice_date=date.today(),
                         total_amount=Decimal("1500.00"), submitted_by_id=user.id)
        db.add(inv2)
        await db.flush()
        db.add(APInvoiceLine(id=uuid.uuid4(), invoice_id=inv2.id, line_no=1, po_line_id=po_line.id,
                             description="Widgets", quantity=100, unit_price=Decimal("15.00"), gl_account_id=gl.id))
        await db.flush()
        r2 = await match_invoice(db, invoice_id=inv2.id)
        assert r2["overall_status"] == "price_variance"
        assert r2["lines"][0]["price_delta_pct"] == pytest.approx(50.0)

        # Case 3: missing receipt — invoice references a PO line never received against
        inv3 = APInvoice(id=uuid.uuid4(), invoice_number="INV-NORECEIPT", vendor_id=vendor.id,
                         purchase_order_id=po.id, invoice_date=date.today(),
                         total_amount=Decimal("1000.00"), submitted_by_id=user.id)
        db.add(inv3)
        await db.flush()
        db.add(APInvoiceLine(id=uuid.uuid4(), invoice_id=inv3.id, line_no=1, po_line_id=po_line2.id,
                             description="Gadgets", quantity=50, unit_price=Decimal("20.00"), gl_account_id=gl.id))
        await db.flush()
        r3 = await match_invoice(db, invoice_id=inv3.id)
        assert r3["overall_status"] == "missing_receipt"

        await db.rollback()  # leave no trace in the dev DB
