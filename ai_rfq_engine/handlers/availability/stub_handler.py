#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Deterministic availability/hold handler for tests and pilot configuration."""

from __future__ import annotations

__author__ = "bibow"

from typing import Any, Optional

import pendulum

from .base import (
    AvailabilityHandler,
    AvailabilityRequest,
    AvailabilityResponse,
    UnknownHoldError,
)


class StubAvailabilityHandler(AvailabilityHandler):
    """
    Resolve a configured response from ``extra_config["fixtures"]``.

    The handler first looks for ``"<provider_item_uuid>#<batch_no>"`` and then
    falls back to ``"<provider_item_uuid>"``. A missing fixture is unavailable.
    """

    def check(
        self,
        *,
        request: AvailabilityRequest,
        config: Any,
        credential: Optional[str],
    ) -> AvailabilityResponse:
        _ = credential  # The deterministic stub makes no outbound authenticated call.
        return self._response("check", request, config, include_hold=False)

    def acquire_hold(
        self,
        *,
        request: AvailabilityRequest,
        config: Any,
        credential: Optional[str],
    ) -> AvailabilityResponse:
        _ = credential  # The deterministic stub makes no outbound authenticated call.
        return self._response("acquire_hold", request, config, include_hold=True)

    def release_hold(
        self,
        *,
        request: AvailabilityRequest,
        config: Any,
        credential: Optional[str],
    ) -> AvailabilityResponse:
        _ = credential  # The deterministic stub makes no outbound authenticated call.
        return self._settle_hold("release_hold", request, config)

    def confirm_hold(
        self,
        *,
        request: AvailabilityRequest,
        config: Any,
        credential: Optional[str],
    ) -> AvailabilityResponse:
        _ = credential  # The deterministic stub makes no outbound authenticated call.
        return self._settle_hold("confirm_hold", request, config)

    def _response(
        self,
        operation: str,
        request: AvailabilityRequest,
        config: Any,
        *,
        include_hold: bool,
    ) -> AvailabilityResponse:
        extra, fixture = self._find_fixture(request, config)
        available = bool(fixture.get("available", False))

        return {
            "system": getattr(config, "system_code", "stub"),
            "operation": operation,
            "request": request,
            "available": available,
            "hold_token": (
                fixture.get("hold_token") if include_hold and available else None
            ),
            "expires_at": (
                fixture.get("expires_at") if include_hold and available else None
            ),
            "fetched_at": pendulum.now("UTC").to_iso8601_string(),
            "ttl_seconds": extra.get("ttl_seconds"),
            "payload": fixture.get("payload"),
        }

    def _settle_hold(
        self,
        operation: str,
        request: AvailabilityRequest,
        config: Any,
    ) -> AvailabilityResponse:
        provided_token = request.get("hold_token")
        extra, fixture = self._find_fixture(request, config)
        expected_token = fixture.get("hold_token")
        if (
            not fixture.get("available", False)
            or not provided_token
            or not expected_token
            or provided_token != expected_token
        ):
            raise UnknownHoldError(
                f"Cannot {operation.replace('_', ' ')} for an unknown hold token",
                details={"provider_item_uuid": request.get("provider_item_uuid")},
            )
        return {
            "system": getattr(config, "system_code", "stub"),
            "operation": operation,
            "request": request,
            "available": bool(fixture.get("available", False)),
            "hold_token": provided_token,
            "expires_at": fixture.get("expires_at"),
            "fetched_at": pendulum.now("UTC").to_iso8601_string(),
            "ttl_seconds": extra.get("ttl_seconds"),
            "payload": fixture.get("payload"),
        }

    def _find_fixture(
        self, request: AvailabilityRequest, config: Any
    ) -> tuple[dict, dict]:
        extra = self._extract_extra_config(config)
        fixtures = (extra.get("fixtures") if isinstance(extra, dict) else None) or {}
        provider_item_uuid = request["provider_item_uuid"]
        batch_no = request.get("batch_no")
        key = f"{provider_item_uuid}#{batch_no}" if batch_no else None
        fixture = fixtures.get(key) if key else None
        if fixture is None:
            fixture = fixtures.get(provider_item_uuid, {"available": False})
        return extra if isinstance(extra, dict) else {}, fixture

    @staticmethod
    def _extract_extra_config(config: Any) -> Any:
        extra = getattr(config, "extra_config", None)
        if extra is None and isinstance(config, dict):
            extra = config.get("extra_config")
        if extra is None:
            return {}
        as_dict = getattr(extra, "as_dict", None)
        if callable(as_dict):
            try:
                return as_dict()
            except Exception:
                return {}
        return extra
