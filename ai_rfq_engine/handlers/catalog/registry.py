#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Catalog handler registry + dispatch.

Concrete handlers register themselves at import time via ``register_handler``.
The ``dispatch_inquire`` entry point orchestrates the full G7b flow:

    config resolution (G7c)  ->  credential resolution  ->  handler.inquire(...)

with structured errors surfaced as ``CatalogHandlerError`` subclasses. Callers
above the GraphQL layer should map the error ``code`` to a typed response field
rather than re-raising — see ``schema.py`` for the wiring.
"""
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
    CatalogHandler,
    CatalogReference,
    CatalogResponse,
    NotConfiguredError,
)

_HANDLERS: Dict[str, Type[CatalogHandler]] = {}


def register_handler(adapter_id: str, handler_cls: Type[CatalogHandler]) -> None:
    """
    Register a catalog handler class under an adapter id.

    ``adapter_id`` typically matches ``system_code`` (e.g. ``"neo4j"``), but
    callers can register multiple adapters for the same system family and pick
    one per-tenant via the config row's ``adapter_id`` field. The registry holds
    classes (not instances) so callers don't accidentally share per-instance
    state across tenants.
    """
    if not isinstance(adapter_id, str) or not adapter_id:
        raise ValueError("adapter_id must be a non-empty string")
    if not isinstance(handler_cls, type) or not issubclass(handler_cls, CatalogHandler):
        raise TypeError("handler_cls must be a CatalogHandler subclass")
    _HANDLERS[adapter_id] = handler_cls


def get_handler(adapter_id: str) -> Optional[Type[CatalogHandler]]:
    """Return the registered handler class for an adapter id, or None."""
    return _HANDLERS.get(adapter_id)


def registered_handlers() -> Dict[str, Type[CatalogHandler]]:
    """Return a snapshot of the registry. Useful in tests and introspection."""
    return dict(_HANDLERS)


def clear_handlers() -> None:
    """
    Remove all registered handlers. Intended for test isolation only.
    Production code should never call this.
    """
    _HANDLERS.clear()


def _auth_required(auth_strategy: Optional[str]) -> bool:
    """A credential is required for every auth_strategy except ``'none'``."""
    return (auth_strategy or "").lower() != "none"


def dispatch_inquire(
    info: ResolveInfo,
    *,
    system_code: str,
    namespace: str = "DEFAULT",
    node_id: Optional[str] = None,
    provider_corp_external_id: Optional[str] = None,
    query: Optional[Any] = None,
) -> CatalogResponse:
    """
    Resolve config, resolve credential, look up handler, and inquire.

    Raises:
        NotConfiguredError: no active config row matches, or no handler is
            registered for the resolved ``adapter_id`` / ``system_code``.
        AuthUnavailableError: the config requires auth but no credential could
            be resolved (neither ``auth_secret_value`` nor a backed
            ``auth_secret_ref``).
        SystemTimeoutError, SystemError, UnknownNodeError: raised by the
            concrete handler. Propagated unchanged.
    """
    config = resolve_external_system_model_for(
        info,
        system_kind="catalog_inquiry",
        system_code=system_code,
        namespace=namespace,
        provider_corp_external_id=provider_corp_external_id,
    )
    if config is None:
        raise NotConfiguredError(
            f"No active catalog_inquiry config for system_code={system_code!r} "
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
            f"a credential but none was resolvable",
            details={
                "system_code": system_code,
                "namespace": namespace,
                "auth_strategy": getattr(config, "auth_strategy", None),
            },
        )

    reference: CatalogReference = {
        "system_code": system_code,
        "namespace": namespace,
        "node_id": node_id,
    }
    handler = handler_cls()
    return handler.inquire(
        reference=reference,
        config=config,
        credential=credential,
        query=query,
    )
