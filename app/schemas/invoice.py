from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class InvoiceLineCreate(BaseModel):
    line_no: int
    po_line_id: uuid.UUID | None = None
    description: str = Field(min_length=1, max_length=512)
    quantity: float = Field(gt=0)
    unit_price: Decimal = Field(gt=0)
    gl_account_id: uuid.UUID


class InvoiceCreate(BaseModel):
    invoice_number: str = Field(min_length=1, max_length=64)
    vendor_id: uuid.UUID
    purchase_order_id: uuid.UUID | None = None
    invoice_date: date
    due_date: date | None = None
    lines: list[InvoiceLineCreate] = Field(min_length=1)

    @field_validator("lines")
    @classmethod
    def _lines_have_unique_numbers(cls, v: list[InvoiceLineCreate]) -> list[InvoiceLineCreate]:
        nums = [line.line_no for line in v]
        if len(nums) != len(set(nums)):
            raise ValueError("line_no values must be unique within an invoice")
        return v


class InvoiceLineResponse(BaseModel):
    id: uuid.UUID
    line_no: int
    description: str
    quantity: float
    unit_price: Decimal
    line_total: Decimal

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    invoice_number: str
    vendor_id: uuid.UUID
    total_amount: Decimal
    status: str
    match_status: str
    duplicate_check_status: str
    invoice_date: date
    created_at: datetime
    lines: list[InvoiceLineResponse] = []

    model_config = {"from_attributes": True}


class DuplicateWarning(BaseModel):
    candidate_invoice_id: uuid.UUID
    candidate_invoice_number: str
    similarity: float
    amount_delta: Decimal
    days_apart: int
