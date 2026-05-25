#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Handler telemetry: structured audit events for availability and catalog operations.

Emits log events with operation metadata so deployment-side metrics pipelines
can aggregate latency, error rate, tenant/partition volume, and namespace
distribution without requiring a separate metrics SDK.

Usage::

    from ai_rfq_engine.handlers.telemetry import emit_handler_event

    emit_handler_event(
        info,
        operation="check",
        handler="availability",
        duration_ms=42.3,
        tenant="tenant#acme",
        namespace="DEFAULT",
        error_code=None,
    )
"""
from __future__ import annotations

__author__ = "bibow"

import time
from contextlib import contextmanager
from typing import Any, Dict, Optional


def emit_handler_event(
    info: Any,
    *,
    operation: str,
    handler: str,
    duration_ms: Optional[float] = None,
    tenant: Optional[str] = None,
    namespace: Optional[str] = None,
    error_code: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Emit a structured log event for handler observability.

    Fields are chosen to match Priority 3 requirements in the gap plan:
    operation, handler, duration, tenant partition, namespace, and error code.
    """
    logger = getattr(info, "context", {}).get("logger")
    if not logger:
        return

    event = {
        "handler_event": True,
        "handler": handler,
        "operation": operation,
        "tenant": tenant or getattr(info, "context", {}).get("partition_key"),
        "namespace": namespace,
        "error_code": error_code,
    }
    if duration_ms is not None:
        event["duration_ms"] = round(duration_ms, 3)
    if extra:
        event.update(extra)

    if error_code:
        logger.warning("handler_telemetry: %s", event)
    else:
        logger.info("handler_telemetry: %s", event)


@contextmanager
def measure_handler_duration(
    info: Any,
    *,
    operation: str,
    handler: str,
    tenant: Optional[str] = None,
    namespace: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
):
    """
    Context manager that measures wall-clock duration and emits a telemetry
    event on success or failure.

    Example::

        with measure_handler_duration(info, operation="acquire_hold",
                                       handler="availability"):
            result = _acquire_hold(info, **kwargs)
    """
    start = time.monotonic()
    error_code = None
    try:
        yield
    except Exception as exc:
        error_code = getattr(exc, "code", "system_error")
        raise
    finally:
        duration_ms = (time.monotonic() - start) * 1000
        emit_handler_event(
            info,
            operation=operation,
            handler=handler,
            duration_ms=duration_ms,
            tenant=tenant,
            namespace=namespace,
            error_code=error_code,
            extra=extra,
        )