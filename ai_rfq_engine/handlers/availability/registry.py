#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Availability handler registry and configuration-backed dispatcher."""
from __future__ import annotations

__author__ = "bibow"

from typing import Any, Dict, Optional, Type

from graphene import ResolveInfo

from ...models.external_system_config import (
    resolve_credential_for,
    resolve_external_system_model_for,
)
from .base import (
    AuthUnavailableError,
    AvailabilityHandler,
    AvailabilityRequest,
    AvailabilityResponse,
    NotConfiguredError,
)

_HANDLERS: Dict[str, Type[AvailabilityHandler]] = {}


def register_handler(adapter_id: str, handler_cls: Type[AvailabilityHandler]) -> None:
    if not isinstance(adapter_id, str) or not adapter_id:
        raise ValueError("adapter_id must be a non-empty string")
    if not isinstance(handler_cls, type) or not issubclass(
        handler_cls, AvailabilityHandler
    ):
        raise TypeError("handler_cls must be an AvailabilityHandler subclass")
    _HANDLERS[adapter_id] = handler_cls


def get_handler(adapter_id: str) -> Optional[Type[AvailabilityHandler]]:
    return _HANDLERS.get(adapter_id)


def registered_handlers() -> Dict[str, Type[AvailabilityHandler]]:
    return dict(_HANDLERS)


def clear_handlers() -> None:
    _HANDLERS.clear()


def _auth_required(auth_strategy: Optional[str]) -> bool:
    return (auth_strategy or "").lower() != "none"


def _dispatch(
    info: ResolveInfo,
    *,
    operation: str,
    system_code: str,
    provider_item_uuid: str,
    service_start_at: Any = None,
    service_end_at: Any = None,
    namespace: str = "DEFAULT",
    provider_corp_external_id: Optional[str] = None,
    batch_no: Optional[str] = None,
    pax_breakdown: Optional[Any] = None,
    qty: Optional[float] = None,
    hold_token: Optional[str] = None,
) -> AvailabilityResponse:
    config = resolve_external_system_model_for(
        info,
        system_kind="availability",
        system_code=system_code,
        namespace=namespace,
        provider_corp_external_id=provider_corp_external_id,
    )
    if config is None:
        raise NotConfiguredError(
            f"No active availability config for system_code={system_code!r} "
            f"namespace={namespace!r}",
            details={
                "system_code": system_code,
                "namespace": namespace,
                "provider_corp_external_id": provider_corp_external_id,
            },
        )

    adapter_id = getattr(config, "adapter_id", None) or system_code
    handler_cls = get_handler(adapter_id)
    if handler_cls is None:
        raise NotConfiguredError(
            f"No handler registered for adapter_id={adapter_id!r}",
            details={
                "adapter_id": adapter_id,
                "system_code": system_code,
                "namespace": namespace,
            },
        )

    credential = resolve_credential_for(config)
    if _auth_required(getattr(config, "auth_strategy", None)) and not credential:
        raise AuthUnavailableError(
            f"auth_strategy={getattr(config, 'auth_strategy', None)!r} requires "
            "a credential but none was resolvable",
            details={
                "system_code": system_code,
                "namespace": namespace,
                "auth_strategy": getattr(config, "auth_strategy", None),
            },
        )

    request: AvailabilityRequest = {
        "provider_item_uuid": provider_item_uuid,
        "batch_no": batch_no,
        "service_start_at": service_start_at,
        "service_end_at": service_end_at,
        "pax_breakdown": pax_breakdown,
        "qty": qty,
        "hold_token": hold_token,
    }
    handler = handler_cls()
    return getattr(handler, operation)(
        request=request,
        config=config,
        credential=credential,
    )


def dispatch_check(info: ResolveInfo, **kwargs: Any) -> AvailabilityResponse:
    return _dispatch(info, operation="check", **kwargs)


def dispatch_acquire_hold(info: ResolveInfo, **kwargs: Any) -> AvailabilityResponse:
    return _dispatch(info, operation="acquire_hold", **kwargs)


def dispatch_release_hold(info: ResolveInfo, **kwargs: Any) -> AvailabilityResponse:
    return _dispatch(info, operation="release_hold", **kwargs)


def dispatch_confirm_hold(info: ResolveInfo, **kwargs: Any) -> AvailabilityResponse:
    return _dispatch(info, operation="confirm_hold", **kwargs)
