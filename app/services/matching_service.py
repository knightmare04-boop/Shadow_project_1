"""Three-way match: PO <-> goods receipt <-> invoice. The report's own FR
list names this explicitly, and it is a genuine fraud control, not ERP
decoration — an invoice with no corresponding PO/receipt, or one billed
above what was ordered/received, is exactly the invoice-kickback pattern
the research project's synth_erp fraud typology models.

Tolerance: price and quantity variance are checked against a percentage
tolerance, taken from the PO (if set) else a tenant-wide default. Within
tolerance -> matched; a PO line with no goods receipt at all -> missing
receipt (cannot pay for what was never received); a variance outside
tolerance is reported, never silently auto-approved.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import APInvoiceLine
from app.models.procurement import GoodsReceiptLine, PurchaseOrderLine
from app.models.types import MatchStatus

DEFAULT_PRICE_TOLERANCE_PCT = Decimal("5.0")
DEFAULT_QTY_TOLERANCE_PCT = Decimal("2.0")


async def match_invoice_line(
    db: AsyncSession, *, invoice_line: APInvoiceLine, po_price_tolerance_pct: Decimal | None,
    po_qty_tolerance_pct: Decimal | None,
) -> tuple[MatchStatus, dict]:
    """Matches ONE invoice line against its referenced PO line + cumulative
    goods received for that PO line. Returns (status, detail)."""
    if invoice_line.po_line_id is None:
        return MatchStatus.missing_po, {"reason": "invoice line has no purchase_order_line reference"}

    po_line = await db.get(PurchaseOrderLine, invoice_line.po_line_id)
    if po_line is None:
        return MatchStatus.missing_po, {"reason": f"PO line {invoice_line.po_line_id} not found"}

    receipt_qty = await db.scalar(
        select(GoodsReceiptLine.quantity_received)
        .where(GoodsReceiptLine.po_line_id == po_line.id)
    ) or Decimal("0")
    total_received = (await db.scalars(
        select(GoodsReceiptLine.quantity_received).where(GoodsReceiptLine.po_line_id == po_line.id)
    )).all()
    total_received_qty = sum((Decimal(str(q)) for q in total_received), start=Decimal("0"))

    if total_received_qty <= 0:
        return MatchStatus.missing_receipt, {
            "po_line_id": str(po_line.id), "ordered_qty": po_line.quantity_ordered, "received_qty": 0,
        }

    price_tol = po_price_tolerance_pct or DEFAULT_PRICE_TOLERANCE_PCT
    qty_tol = po_qty_tolerance_pct or DEFAULT_QTY_TOLERANCE_PCT

    price_delta_pct = abs(invoice_line.unit_price - po_line.unit_price) / po_line.unit_price * 100 \
        if po_line.unit_price else Decimal("0")
    invoice_qty = Decimal(str(invoice_line.quantity))
    qty_delta_pct = abs(invoice_qty - total_received_qty) / total_received_qty * 100 \
        if total_received_qty else Decimal("100")

    detail = {
        "po_line_id": str(po_line.id),
        "po_unit_price": str(po_line.unit_price), "invoice_unit_price": str(invoice_line.unit_price),
        "price_delta_pct": round(float(price_delta_pct), 2),
        "received_qty": float(total_received_qty), "invoice_qty": float(invoice_qty),
        "qty_delta_pct": round(float(qty_delta_pct), 2),
    }

    if price_delta_pct > price_tol:
        return MatchStatus.price_variance, detail
    if qty_delta_pct > qty_tol:
        return MatchStatus.quantity_variance, detail
    return MatchStatus.matched, detail


async def match_invoice(db: AsyncSession, *, invoice_id: uuid.UUID,
                        po_price_tolerance_pct: Decimal | None = None,
                        po_qty_tolerance_pct: Decimal | None = None) -> dict:
    """Matches every line of an invoice; the invoice's overall match_status
    is the WORST line result (matched < variance < missing — any problem on
    any line blocks the whole invoice from being clean)."""
    lines = (await db.scalars(
        select(APInvoiceLine).where(APInvoiceLine.invoice_id == invoice_id)
    )).all()

    severity = {
        MatchStatus.matched: 0, MatchStatus.price_variance: 1, MatchStatus.quantity_variance: 1,
        MatchStatus.missing_receipt: 2, MatchStatus.missing_po: 2, MatchStatus.not_attempted: 0,
    }
    worst = MatchStatus.matched
    line_results = []
    for line in lines:
        status, detail = await match_invoice_line(
            db, invoice_line=line, po_price_tolerance_pct=po_price_tolerance_pct,
            po_qty_tolerance_pct=po_qty_tolerance_pct,
        )
        line_results.append({"line_id": str(line.id), "line_no": line.line_no, "status": status.value, **detail})
        if severity[status] > severity[worst]:
            worst = status

    return {"invoice_id": str(invoice_id), "overall_status": worst.value, "lines": line_results}
