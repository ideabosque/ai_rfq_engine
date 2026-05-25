#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Availability hold expiry scanner.

Scans ``AvailabilityHoldModel`` for ``held`` records past their
``expires_at`` and invokes ``dispatch_expire_hold`` to restore capacity.
Designed to be called from a scheduled invoker (Lambda, EventBridge, cron).

Usage::

    from ai_rfq_engine.handlers.availability.expiry_scanner import scan_expired_holds

    result = scan_expired_holds(logger, partition_key="tenant#acme")
    # result = {"scanned": 42, "expired": 3, "errors": 0}
"""
from __future__ import annotations

__author__ = "bibow"

import logging
from types import SimpleNamespace
from typing import Any, Dict, Optional

import pendulum
from pynamodb.exceptions import DoesNotExist


def _scan_held_records(partition_key: str):
    """Query AvailabilityHoldModel for held records past their expires_at."""
    from ai_rfq_engine.models.availability_hold import AvailabilityHoldModel

    now = pendulum.now("UTC")
    return AvailabilityHoldModel.query(
        partition_key,
        filter_condition=(
            (AvailabilityHoldModel.status == AvailabilityHoldModel.HELD)
            & (AvailabilityHoldModel.expires_at < now)
        ),
    )


def scan_expired_holds(
    logger: logging.Logger,
    *,
    partition_key: str,
    batch_size: int = 100,
    dry_run: bool = False,
    info: Optional[Any] = None,
    _query_fn: Optional[Any] = None,
) -> Dict[str, int]:
    """
    Scan for expired ``held`` records and invoke the expiry operation.

    Parameters
    ----------
    logger : logging.Logger
        Application logger for audit output.
    partition_key : str
        Tenant partition key to scan.
    batch_size : int
        Maximum records to process in one invocation (default 100).
    dry_run : bool
        When True, log what *would* be expired without actually calling
        ``dispatch_expire_hold``. Useful for manual inspection before
        enabling the scanner in production.
    info : Optional[Any]
        A ``ResolveInfo``-compatible object carrying ``context``. When omitted,
        the scanner creates the minimal context required for hold expiry.
    _query_fn : Optional[Any]
        Override the query function for testing. Defaults to
        ``_scan_held_records``.

    Returns
    -------
    dict
        Counts: ``{"scanned": int, "expired": int, "errors": int}``
    """
    from .handler import UnknownHoldError, dispatch_expire_hold

    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")
    if not dry_run:
        if info is None:
            info = SimpleNamespace(
                context={"partition_key": partition_key, "logger": logger}
            )
        elif getattr(info, "context", {}).get("partition_key") != partition_key:
            raise ValueError("info.context partition_key must match partition_key")

    scanned = 0
    expired = 0
    errors = 0

    query_fn = _query_fn or _scan_held_records

    try:
        iterator = query_fn(partition_key)
    except Exception as exc:
        logger.error("expiry_scanner: scan failed for partition_key=%s: %s", partition_key, exc)
        return {"scanned": 0, "expired": 0, "errors": 1}

    for hold in iterator:
        if scanned >= batch_size:
            logger.info(
                "expiry_scanner: batch_size limit reached (%d), stopping", batch_size
            )
            break
        scanned += 1

        token = hold.hold_token
        provider_item_uuid = hold.provider_item_uuid
        batch_no = getattr(hold, "batch_no", None)

        logger.info(
            "expiry_scanner: found expired hold token=%s provider_item=%s "
            "batch_no=%s expired_at=%s",
            token,
            provider_item_uuid,
            batch_no,
            hold.expires_at,
        )

        if dry_run:
            expired += 1
            continue

        try:
            dispatch_expire_hold(
                info,
                provider_item_uuid=provider_item_uuid,
                batch_no=batch_no,
                hold_token=token,
            )
            expired += 1
            logger.info("expiry_scanner: expired hold token=%s", token)
        except UnknownHoldError as exc:
            logger.warning(
                "expiry_scanner: hold token=%s already transitioned: %s", token, exc
            )
            expired += 1
        except Exception as exc:
            errors += 1
            logger.error(
                "expiry_scanner: failed to expire hold token=%s: %s", token, exc
            )

    logger.info(
        "expiry_scanner: partition_key=%s scanned=%d expired=%d errors=%d",
        partition_key,
        scanned,
        expired,
        errors,
    )
    return {"scanned": scanned, "expired": expired, "errors": errors}
