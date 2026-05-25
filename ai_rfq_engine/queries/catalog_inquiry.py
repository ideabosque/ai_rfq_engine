#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
GraphQL resolver for KGE-backed ``inquire_catalog`` (G7b).

Wraps ``handlers.catalog.dispatch_inquire`` and translates structured
``CatalogHandlerError`` subclasses into in-band ``CatalogInquiryResultType``
fields. Graph-instance configuration and credentials remain owned by KGE.
"""
from __future__ import annotations

__author__ = "bibow"

import pendulum
from typing import Any, Dict, Optional

from graphene import ResolveInfo

from ..handlers.catalog import (
    CatalogHandlerError,
    dispatch_inquire,
)
from ..types.catalog_inquiry import CatalogInquiryResultType


def _parse_fetched_at(value: Optional[str]):
    """
    Convert the handler's ISO-8601 string to a pendulum/datetime instance for
    the GraphQL ``DateTime`` field. Returns ``None`` if parsing fails so a
    malformed handler response degrades gracefully.
    """
    if not value:
        return None
    try:
        return pendulum.parse(value)
    except Exception:
        return None


def resolve_inquire_catalog(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> CatalogInquiryResultType:
    namespace = kwargs.get("namespace") or "DEFAULT"
    node_id = kwargs.get("node_id")
    query = kwargs.get("query")

    try:
        result = dispatch_inquire(
            info,
            namespace=namespace,
            node_id=node_id,
            query=query,
        )
    except CatalogHandlerError as exc:
        return CatalogInquiryResultType(
            namespace=namespace,
            node_id=node_id,
            payload=None,
            fetched_at=None,
            ttl_seconds=None,
            error_code=exc.code,
            error_message=str(exc),
        )

    ref = result.get("ref") or {}
    return CatalogInquiryResultType(
        namespace=ref.get("namespace", namespace),
        node_id=ref.get("node_id", node_id),
        payload=result.get("payload"),
        fetched_at=_parse_fetched_at(result.get("fetched_at")),
        ttl_seconds=result.get("ttl_seconds"),
        error_code=None,
        error_message=None,
    )
