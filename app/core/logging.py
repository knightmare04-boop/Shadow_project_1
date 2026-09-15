"""Structured JSON logging with correlation-id propagation (Module 8 hardening
item #12 — Error logging). Every log line, from the access log through the DB
layer to the fraud-scoring call, carries the same ``correlation_id`` so a
GlitchTip event can be joined back to the request that caused it.
"""
from __future__ import annotations

import contextvars
import logging
import sys
import uuid

import structlog

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


def new_correlation_id() -> str:
    cid = str(uuid.uuid4())
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def set_correlation_id(cid: str) -> None:
    _correlation_id.set(cid)


def _add_correlation_id(logger, method_name, event_dict):
    cid = _correlation_id.get()
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


# Fields that must never reach a log line, even accidentally passed as a kwarg.
_REDACT_KEYS = {
    "password", "secret", "token", "authorization", "api_key", "access_token",
    "refresh_token", "secret_key", "database_url", "neo4j_password",
}


def _redact_sensitive(logger, method_name, event_dict):
    for key in list(event_dict.keys()):
        if key.lower() in _REDACT_KEYS:
            event_dict[key] = "***REDACTED***"
    return event_dict


def configure_logging(*, json_logs: bool = True, level: int = logging.INFO) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        _add_correlation_id,
        _redact_sensitive,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.processors.JSONRenderer()
            if json_logs
            else structlog.dev.ConsoleRenderer()
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
