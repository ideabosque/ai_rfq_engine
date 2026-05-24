#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Shared contract and structured failures for availability handlers."""
from __future__ import annotations

__author__ = "bibow"

from abc import ABC, abstractmethod
from typing import Any, Optional, TypedDict


class _RequiredAvailabilityRequest(TypedDict):
    provider_item_uuid: str


class AvailabilityRequest(_RequiredAvailabilityRequest, total=False):
    batch_no: Optional[str]
    service_start_at: Any
    service_end_at: Any
    pax_breakdown: Optional[Any]
    qty: Optional[float]
    hold_token: Optional[str]


class AvailabilityResponse(TypedDict, total=False):
    system: str
    operation: str
    request: AvailabilityRequest
    available: bool
    hold_token: Optional[str]
    expires_at: Optional[str]
    fetched_at: str
    ttl_seconds: Optional[int]
    payload: Any


class AvailabilityHandler(ABC):
    """Abstract base for in-engine availability and temporary-hold handlers."""

    @abstractmethod
    def check(
        self,
        *,
        request: AvailabilityRequest,
        config: Any,
        credential: Optional[str],
    ) -> AvailabilityResponse:
        """Check capacity without changing external inventory state."""

    def acquire_hold(
        self,
        *,
        request: AvailabilityRequest,
        config: Any,
        credential: Optional[str],
    ) -> AvailabilityResponse:
        raise OperationUnsupportedError("This adapter does not support hold acquisition")

    def release_hold(
        self,
        *,
        request: AvailabilityRequest,
        config: Any,
        credential: Optional[str],
    ) -> AvailabilityResponse:
        raise OperationUnsupportedError("This adapter does not support hold release")

    def confirm_hold(
        self,
        *,
        request: AvailabilityRequest,
        config: Any,
        credential: Optional[str],
    ) -> AvailabilityResponse:
        raise OperationUnsupportedError("This adapter does not support hold confirmation")


class AvailabilityHandlerError(Exception):
    code: str = "system_error"

    def __init__(self, message: str = "", *, details: Optional[dict] = None) -> None:
        super().__init__(message or self.__class__.__name__)
        self.details = details or {}


class NotConfiguredError(AvailabilityHandlerError):
    code = "not_configured"


class AuthUnavailableError(AvailabilityHandlerError):
    code = "auth_unavailable"


class OperationUnsupportedError(AvailabilityHandlerError):
    code = "operation_unsupported"


class UnknownHoldError(AvailabilityHandlerError):
    code = "unknown_hold"


class SystemTimeoutError(AvailabilityHandlerError):
    code = "system_timeout"


class SystemError(AvailabilityHandlerError):
    code = "system_error"
