"""The forensic console's alert queue — UC4 (Inspect High-Risk Audit Alerts)
and the auditor feedback loop from BCSE497J §4.2.3's AuditAlert domain
class notes (the piece the demo HTML has no equivalent of)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_role
from app.core.errors import NotFoundError, ValidationAppError
from app.db.session import get_db
from app.models.audit import AuditAlert, AuditLog
from app.models.types import ReviewFeedbackStatus, UserRoleName
from app.models.user import AppUser
from app.schemas.alert import AlertFeedbackRequest, AlertResponse

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

_CAN_REVIEW = require_role(UserRoleName.forensic_auditor, UserRoleName.system_administrator)


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    db: AsyncSession = Depends(get_db), _: AppUser = Depends(get_current_user),
    feedback_status: str | None = None, limit: int = 50, cursor: uuid.UUID | None = None,
) -> list[AlertResponse]:
    stmt = select(AuditAlert).order_by(AuditAlert.score.desc()).limit(min(limit, 200))
    if feedback_status is not None:
        stmt = stmt.where(AuditAlert.feedback_status == feedback_status)
    if cursor is not None:
        stmt = stmt.where(AuditAlert.id > cursor)
    alerts = (await db.scalars(stmt)).all()
    return [AlertResponse.model_validate(a) for a in alerts]


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: AppUser = Depends(get_current_user),
) -> AlertResponse:
    alert = await db.get(AuditAlert, alert_id)
    if alert is None:
        raise NotFoundError(f"alert {alert_id} not found")
    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/feedback", response_model=AlertResponse)
async def submit_feedback(
    alert_id: uuid.UUID, payload: AlertFeedbackRequest,
    db: AsyncSession = Depends(get_db), actor: AppUser = Depends(_CAN_REVIEW),
) -> AlertResponse:
    alert = await db.get(AuditAlert, alert_id)
    if alert is None:
        raise NotFoundError(f"alert {alert_id} not found")
    try:
        status = ReviewFeedbackStatus(payload.feedback_status)
    except ValueError:
        raise ValidationAppError(
            f"invalid feedback_status {payload.feedback_status!r}; "
            f"must be one of {[s.value for s in ReviewFeedbackStatus]}",
        )

    alert.feedback_status = status
    alert.feedback_note = payload.feedback_note
    alert.feedback_by_id = actor.id
    alert.feedback_at = datetime.now(timezone.utc)

    db.add(AuditLog(
        actor_user_id=actor.id, action="alert.feedback", entity_type="audit_alert",
        entity_id=alert.id, detail={"feedback_status": status.value, "note": payload.feedback_note},
    ))
    await db.commit()
    await db.refresh(alert)
    return AlertResponse.model_validate(alert)
