#!/usr/bin/python
# -*- coding: utf-8 -*-
"""GraphQL resolver for availability operations using local ProviderItemBatch data."""
from __future__ import annotations

__author__ = "bibow"

from typing import Any, Dict, Optional

import pendulum
from graphene import ResolveInfo

from ..handlers.availability import AvailabilityHandlerError, dispatch_check
from ..types.availability import AvailabilityResultType


def _parse_time(value: Optional[Any]):
    if not value:
        return None
    if not isinstance(value, str):
        return value
    try:
        return pendulum.parse(value)
    except Exception:
        return None


def _result_from_dispatch(info: ResolveInfo, dispatch, **kwargs: Dict[str, Any]) -> AvailabilityResultType:
    try:
        result = dispatch(
            info,
            provider_item_uuid=kwargs["provider_item_uuid"],
            batch_no=kwargs.get("batch_no"),
            service_start_at=kwargs.get("service_start_at"),
            service_end_at=kwargs.get("service_end_at"),
            pax_breakdown=kwargs.get("pax_breakdown"),
            qty=kwargs.get("qty"),
            hold_token=kwargs.get("hold_token"),
        )
    except AvailabilityHandlerError as exc:
        return AvailabilityResultType(
            operation=getattr(dispatch, "__name__", "").removeprefix("dispatch_"),
            provider_item_uuid=kwargs["provider_item_uuid"],
            batch_no=kwargs.get("batch_no"),
            service_start_at=kwargs.get("service_start_at"),
            service_end_at=kwargs.get("service_end_at"),
            available=None,
            error_code=exc.code,
            error_message=str(exc),
        )

    request = result.get("request") or {}
    return AvailabilityResultType(
        operation=result.get("operation"),
        provider_item_uuid=request.get(
            "provider_item_uuid", kwargs["provider_item_uuid"]
        ),
        batch_no=request.get("batch_no", kwargs.get("batch_no")),
        service_start_at=_parse_time(
            request.get("service_start_at", kwargs.get("service_start_at"))
        ),
        service_end_at=_parse_time(
            request.get("service_end_at", kwargs.get("service_end_at"))
        ),
        available=result.get("available"),
        hold_token=result.get("hold_token"),
        expires_at=_parse_time(result.get("expires_at")),
        payload=result.get("payload"),
        fetched_at=_parse_time(result.get("fetched_at")),
        ttl_seconds=result.get("ttl_seconds"),
        error_code=None,
        error_message=None,
    )


def resolve_check_availability(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> AvailabilityResultType:
    return _result_from_dispatch(info, dispatch_check, **kwargs)
