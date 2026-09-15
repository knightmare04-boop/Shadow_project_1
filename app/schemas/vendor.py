from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class VendorCreate(BaseModel):
    vendor_code: str = Field(min_length=1, max_length=32)
    legal_name: str = Field(min_length=1, max_length=256)
    tax_id: str | None = None
    bank_account_masked: str | None = None


class VendorResponse(BaseModel):
    id: uuid.UUID
    vendor_code: str
    legal_name: str
    tax_id: str | None
    is_active: bool
    is_blocked: bool
    created_at: datetime

    model_config = {"from_attributes": True}
