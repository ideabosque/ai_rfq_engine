#!/usr/bin/python
# -*- coding: utf-8 -*-
"""G3 availability and temporary-hold handler boundary."""
from __future__ import annotations

__author__ = "bibow"

from .base import (
    AuthUnavailableError,
    AvailabilityHandler,
    AvailabilityHandlerError,
    AvailabilityResponse,
    NotConfiguredError,
    OperationUnsupportedError,
    UnknownHoldError,
    SystemError as AvailabilitySystemError,
    SystemTimeoutError,
)
from .registry import (
    clear_handlers,
    dispatch_acquire_hold,
    dispatch_check,
    dispatch_confirm_hold,
    dispatch_release_hold,
    get_handler,
    register_handler,
    registered_handlers,
)
from .stub_handler import StubAvailabilityHandler

register_handler("stub", StubAvailabilityHandler)

__all__ = [
    "AuthUnavailableError",
    "AvailabilityHandler",
    "AvailabilityHandlerError",
    "AvailabilityResponse",
    "AvailabilitySystemError",
    "NotConfiguredError",
    "OperationUnsupportedError",
    "UnknownHoldError",
    "SystemTimeoutError",
    "clear_handlers",
    "dispatch_acquire_hold",
    "dispatch_check",
    "dispatch_confirm_hold",
    "dispatch_release_hold",
    "get_handler",
    "register_handler",
    "registered_handlers",
]
