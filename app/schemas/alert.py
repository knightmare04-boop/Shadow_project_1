from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AlertResponse(BaseModel):
    id: uuid.UUID
    dataset: str
    transaction_id: str
    payment_id: uuid.UUID | None
    score: float
    threshold: float
    risk_drivers: list
    graph_evidence: dict
    model_artifact: str
    feedback_status: str
    feedback_note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertFeedbackRequest(BaseModel):
    feedback_status: str  # confirmed_fraud | false_positive | escalated
    feedback_note: str | None = None
