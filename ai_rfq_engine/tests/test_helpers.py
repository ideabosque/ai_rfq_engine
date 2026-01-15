#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Helper functions and decorators for AI RFQ Engine tests."""
from __future__ import annotations

__author__ = "bibow"

import logging
import time
import uuid
from functools import wraps
from typing import Any, Dict, Optional, Tuple

from silvaengine_utility.serializer import Serializer

logger = logging.getLogger("test_ai_rfq_engine")


def call_method(
    engine: Any,
    method_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    label: Optional[str] = None,
) -> Tuple[Optional[Any], Optional[Exception]]:
    """
    Invoke engine methods with consistent logging and error capture.

    Args:
        engine: Engine instance
        method_name: Name of method to call
        arguments: Method arguments
        label: Optional label for logging

    Returns:
        Tuple of (result, error) - one will be None
    """
    arguments = arguments or {}
    op = label or method_name
    cid = uuid.uuid4().hex[:8]  # Correlation ID for tracking

    logger.info(f"Method call: cid={cid} op={op} arguments={arguments}")
    t0 = time.perf_counter()

    try:
        method = getattr(engine, method_name)
    except AttributeError as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            f"Method response: cid={cid} op={op} elapsed_ms={elapsed_ms} "
            f"success=False error={str(exc)}"
        )
        return None, exc

    try:
        result = method(**arguments)
        result = Serializer.json_loads(result["body"]) if "body" in result else result

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            f"Method response: cid={cid} op={op} elapsed_ms={elapsed_ms} "
            f"success=True result={Serializer.json_dumps(result)}"
        )

        # Parse JSON string response if needed (graphql_execute returns JSON string)
        if isinstance(result, (str, bytes)):
            import json

            result = (
                json.loads(result)
                if isinstance(result, str)
                else json.loads(result.decode("utf-8"))
            )

        return result, None
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            f"Method response: cid={cid} op={op} elapsed_ms={elapsed_ms} "
            f"success=False error={str(exc)})"
        )
        return None, exc


def log_test_result(func):
    """
    Decorator to log test execution with timing.

    Usage:
        @log_test_result
        def test_something():
            pass
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        test_name = func.__name__
        logger.info(f"{'='*80}")
        logger.info(f"Starting test: {test_name}")
        logger.info(f"{'='*80}")
        t0 = time.perf_counter()

        try:
            result = func(*args, **kwargs)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.info(f"{'='*80}")
            logger.info(f"Test {test_name} PASSED (elapsed: {elapsed_ms}ms)")
            logger.info(f"{'='*80}\n")
            return result
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.error(f"{'='*80}")
            logger.error(f"Test {test_name} FAILED (elapsed: {elapsed_ms}ms): {exc}")
            logger.error(f"{'='*80}\n")
            raise

    return wrapper


def validate_graphql_result(
    result: Dict[str, Any],
    expected_keys: list[str],
    nested_path: Optional[list[str]] = None,
) -> None:
    """
    Validate that GraphQL operation returned expected structure.

    Args:
        result: GraphQL result dict
        expected_keys: Keys that should exist in result
        nested_path: Path to nested object (e.g., ['data', 'item'])

    Raises:
        AssertionError: If validation fails
    """
    current = result
    path_str = "result"

    # Navigate to nested object if path provided
    if nested_path:
        for key in nested_path:
            assert key in current, f"{path_str} missing key '{key}'"
            current = current[key]
            path_str += f"['{key}']"

    # Validate expected keys exist
    for key in expected_keys:
        assert key in current, f"{path_str} missing expected key '{key}'"

    logger.info(f"Validated structure at {path_str}: {list(current.keys())}")


# Alias for backward compatibility or specific usage context
validate_nested_resolver_result = validate_graphql_result
