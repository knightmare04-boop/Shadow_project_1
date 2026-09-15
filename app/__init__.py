"""The Self-Auditing Ledger — application layer.

A Procure-to-Pay ERP (vendors, POs, goods receipts, AP invoices, payment runs,
double-entry GL) with a forensic audit console fed by the research pipeline in
``src/`` (topology engine, XGBoost models, TreeSHAP, Neo4j replay).

Layout:
    app/core      settings, logging, security primitives
    app/db        SQLAlchemy engine/session, declarative base
    app/models    ORM entities (Module 3)
    app/schemas   Pydantic request/response contracts
    app/api       FastAPI routers (Module 4)
    app/services  domain + fraud-engine integration logic (Module 4-5)

``src/`` is untouched by this package and remains independently runnable as the
research pipeline it always was.
"""
