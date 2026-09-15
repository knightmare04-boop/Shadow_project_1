from __future__ import annotations

import uuid

from pydantic import BaseModel


class GLAccountResponse(BaseModel):
    id: uuid.UUID
    account_code: str
    name: str
    account_type: str
    is_active: bool

    model_config = {"from_attributes": True}
