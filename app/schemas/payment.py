from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    invoice_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    payment_date: date


class PaymentResponse(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID
    vendor_id: uuid.UUID
    amount: Decimal
    status: str
    payment_date: date | None
    failure_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
