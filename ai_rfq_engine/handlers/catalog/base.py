#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Abstract base class and structured error types for G7b catalog inquiry handlers.

Each concrete handler queries one external catalog system. The contract here is
deliberately thin so the same shape can serve any backend (graph, REST, vendor
SDK). The dispatch sequence in ``registry.dispatch_inquire`` does the config
lookup, credential resolution, and error wrapping; the handler only implements
``inquire`` against a live reference + credential.
"""

from __future__ import annotations

__author__ = "bibow"

from abc import ABC, abstractmethod
from typing import Any, Optional, TypedDict


class CatalogReference(TypedDict):
    """Identity triple for an external catalog node."""

    system_code: str
    namespace: str
    node_id: Optional[str]


class CatalogResponse(TypedDict, total=False):
    """
    Normalized envelope returned by every handler.

    Fields:
        system:       echoes the system_code that produced the payload.
        ref:          identity triple (system_code, namespace, node_id) that
                      was looked up; ``node_id`` may be None for browse/search
                      queries that did not pin a single node.
        payload:      handler-specific normalized response. Graph handlers
                      typically return {properties, relationships}; flat REST
                      handlers typically return the record as a dict.
        fetched_at:   ISO-8601 UTC timestamp when the external call returned.
        ttl_seconds:  recommended cache lifetime; ``None`` means the caller
                      should not cache.
    """

    system: str
    ref: CatalogReference
    payload: Any
    fetched_at: str
    ttl_seconds: Optional[int]


class CatalogHandler(ABC):
    """
    Abstract base for in-engine catalog inquiry handlers (G7b).

    Implementations should be effectively stateless: one instance may be reused
    across many inquiries, but per-call state belongs on the stack. Credentials
    received via ``inquire`` must NOT be stored on the instance or logged.
    """

    @abstractmethod
    def inquire(
        self,
        *,
        reference: CatalogReference,
        config: Any,
        credential: Optional[str],
        query: Optional[Any] = None,
    ) -> CatalogResponse:
        """
        Execute one inquiry against the external system.

        Args:
            reference:  identity triple from the caller.
            config:     ExternalSystemConfigModel row (read-only). Provides
                        ``endpoint_url``, ``timeout_seconds``, ``cache_ttl_seconds``,
                        and ``extra_config``.
            credential: plaintext credential resolved from the config, or None
                        when ``auth_strategy = 'none'``. Handlers must use the
                        credential only for the outbound call and never persist
                        or log it.
            query:      handler-specific opaque filter/traversal hint, or None.

        Returns:
            A ``CatalogResponse`` envelope.

        Raises:
            SystemTimeoutError, SystemError, UnknownNodeError as appropriate.
            Handlers should NOT raise NotConfiguredError or AuthUnavailableError;
            those are surfaced by the dispatch wrapper before the handler runs.
        """


# --- Structured errors ------------------------------------------------------ #


class CatalogHandlerError(Exception):
    """
    Base for structured catalog-handler failures.

    Subclasses carry a stable ``code`` string that GraphQL callers can switch
    on without parsing message text. Inspired by gRPC status codes.
    """

    code: str = "system_error"

    def __init__(self, message: str = "", *, details: Optional[dict] = None) -> None:
        super().__init__(message or self.__class__.__name__)
        self.details = details or {}


class NotConfiguredError(CatalogHandlerError):
    """No active ExternalSystemConfig row matched the requested (tenant, system, namespace)."""

    code = "not_configured"


class AuthUnavailableError(CatalogHandlerError):
    """
    ``auth_strategy`` requires a credential but neither ``auth_secret_value``
    nor ``auth_secret_ref`` resolved to one.
    """

    code = "auth_unavailable"


class SystemTimeoutError(CatalogHandlerError):
    """External system exceeded the configured ``timeout_seconds``."""

    code = "system_timeout"


class SystemError(CatalogHandlerError):
    """
    External system returned an error response, or a transport-level failure
    occurred. Concrete handlers should wrap upstream exceptions in this.
    """

    code = "system_error"


class UnknownNodeError(CatalogHandlerError):
    """The referenced node did not exist in the external system."""

    code = "unknown_node"
