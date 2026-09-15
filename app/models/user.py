"""Users + RBAC. The three roles from BCSE497J_Project_I_Report.md §4.2.1:
ERP Clerk (transactional work), Forensic Auditor (the console, read-mostly +
feedback), System Administrator (user/config management, period close).

A single ``role`` column (not a many-to-many roles table) is deliberate: the
report's actor model is three fixed, non-overlapping roles, not an open
permission system. If that changes, this is the file to revisit.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.types import UserRoleName, created_at_col, updated_at_col, uuid_pk


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(256), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[UserRoleName] = mapped_column(String(32), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
