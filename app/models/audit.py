"""Immutable audit log (SOX trail, UC7) and the AuditAlert domain class from
BCSE497J_Project_I_Report.md §4.2.3 — the fraud-engine finding plus the
auditor feedback loop the demo HTML has no equivalent of.

Immutability for AuditLog is enforced at the database level (a rule/trigger
that rejects UPDATE and DELETE — see the same GL-invariants migration) so an
admin console bug or a compromised app-server credential cannot rewrite
history; only INSERT is ever valid on this table.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.types import GUID, ReviewFeedbackStatus, created_at_col, uuid_pk


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = uuid_pk()
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("app_users.id"), index=True)
    action: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="e.g. invoice.approve, payment.post, period.close, alert.feedback",
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    detail: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = created_at_col()


class AuditAlert(Base):
    """One fraud-engine finding for one transaction: calibrated score, exact
    SHAP attribution, verified graph evidence, and the auditor's disposition."""

    __tablename__ = "audit_alerts"
    __table_args__ = (
        # The alert queue's default view is "ranked by score, newest open
        # ones first" — a plain btree DESC index turns that into an index
        # scan instead of a seq-scan-then-sort as the table grows past a
        # trivial row count.
        Index("ix_audit_alerts_score", "score", postgresql_ops={"score": "DESC"}),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    dataset: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    transaction_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # Nullable: an alert may originate from replayed research-dataset
    # transactions (no live Payment row) or from a live posting (linked).
    payment_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("payments.id"), index=True)

    score: Mapped[float] = mapped_column(nullable=False)
    threshold: Mapped[float] = mapped_column(nullable=False)
    rank: Mapped[int | None]
    risk_drivers: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    graph_evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    model_artifact: Mapped[str] = mapped_column(String(64), nullable=False)

    feedback_status: Mapped[ReviewFeedbackStatus] = mapped_column(
        String(32), default=ReviewFeedbackStatus.open, nullable=False, index=True,
    )
    feedback_by_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("app_users.id"))
    feedback_note: Mapped[str | None] = mapped_column(String(1024))
    # Explicit timezone=True: a bare Mapped[datetime] infers TIMESTAMP
    # WITHOUT TIME ZONE, but the app always writes datetime.now(timezone.utc)
    # (aware) — asyncpg then fails encoding with "can't subtract
    # offset-naive and offset-aware datetimes". Found via a live feedback
    # submission during Module 5 testing.
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = created_at_col()
