#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
G7b catalog inquiry handlers.

Each registered handler queries one external catalog system (Neo4j, a REST menu
API, a PMS, an ERP item master) and returns a normalized response envelope. The
public entry point ``dispatch_inquire`` performs the full sequence:

    1. Resolve the G7c ExternalSystemConfig row for (tenant, system_kind,
       system_code, namespace, provider_corp_external_id).
    2. Look up the handler registered for the system_code (or the explicit
       ``adapter_id`` override on the config row).
    3. Resolve the credential per the hybrid inline/external model in
       ``models.external_system_config.resolve_credential_for``.
    4. Invoke the handler with the reference, the (read-only) config, the
       credential, and the opaque per-handler query.
    5. Return the handler's envelope unchanged.

Structured failure modes are raised as ``CatalogHandlerError`` subclasses so
GraphQL callers see a predictable error code rather than an opaque traceback.
"""
from __future__ import annotations

__author__ = "bibow"

from .base import (
    CatalogHandler,
    CatalogResponse,
    CatalogHandlerError,
    NotConfiguredError,
    AuthUnavailableError,
    SystemTimeoutError,
    SystemError as CatalogSystemError,
    UnknownNodeError,
)
from .registry import (
    register_handler,
    get_handler,
    registered_handlers,
    clear_handlers,
    dispatch_inquire,
)
from .stub_handler import StubCatalogHandler
from .neo4j_handler import Neo4jCatalogHandler

register_handler("stub", StubCatalogHandler)
register_handler("neo4j", Neo4jCatalogHandler)

__all__ = [
    "CatalogHandler",
    "CatalogResponse",
    "CatalogHandlerError",
    "NotConfiguredError",
    "AuthUnavailableError",
    "SystemTimeoutError",
    "CatalogSystemError",
    "UnknownNodeError",
    "Neo4jCatalogHandler",
    "StubCatalogHandler",
    "register_handler",
    "get_handler",
    "registered_handlers",
    "clear_handlers",
    "dispatch_inquire",
]
