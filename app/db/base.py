"""Declarative base with an explicit constraint-naming convention.

Without this, Postgres auto-names constraints/indexes unpredictably
(``payments_invoice_id_key`` vs ``uq_payments_invoice_id`` depending on how the
constraint was created), which makes Alembic autogenerate diffs noisy and makes
Module 7's before/after index audit hard to script. Every index and constraint
this app creates gets a name in this convention.
"""
from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
