#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Deterministic stub catalog handler.

Returns a predictable payload from ``config.extra_config['fixtures']`` keyed by
``node_id``. Used by unit tests and as a placeholder for the Phase 4 pilot until
a real Neo4j (or other vendor) handler is implemented and the secrets-manager
decision is made.

To exercise this handler in tests, register it explicitly:

    from ai_rfq_engine.handlers.catalog import register_handler
    from ai_rfq_engine.handlers.catalog.stub_handler import StubCatalogHandler

    register_handler("stub", StubCatalogHandler)

and seed an ExternalSystemConfigModel row with ``system_code='stub'``,
``system_kind='catalog_inquiry'``, ``auth_strategy='none'``, and an
``extra_config`` map of fixtures.
"""
from __future__ import annotations

__author__ = "bibow"

from typing import Any, Optional

import pendulum

from .base import (
    CatalogHandler,
    CatalogReference,
    CatalogResponse,
    SystemError,
    UnknownNodeError,
)


class StubCatalogHandler(CatalogHandler):
    """
    Deterministic test handler. Pulls fixtures from ``config.extra_config``.

    Expected ``extra_config`` shape:
        {
            "fixtures": {
                "<node_id>": { ...payload... },
                ...
            },
            "ttl_seconds": 60  # optional; defaults to None
        }

    If the requested ``node_id`` is None (browse mode), returns the fixture map.
    For deterministic query tests, ``query={"match": {"field": value}}`` limits
    browse-mode fixtures to payload dictionaries matching all given fields.
    """

    def inquire(
        self,
        *,
        reference: CatalogReference,
        config: Any,
        credential: Optional[str],
        query: Optional[Any] = None,
    ) -> CatalogResponse:
        _ = credential  # The deterministic stub makes no outbound authenticated call.
        extra = self._extract_extra_config(config)
        fixtures = (extra.get("fixtures") if isinstance(extra, dict) else None) or {}
        ttl = (extra.get("ttl_seconds") if isinstance(extra, dict) else None)

        node_id = reference.get("node_id")
        if node_id is None:
            payload: Any = self._filter_fixtures(fixtures, query)
        else:
            if query:
                raise SystemError(
                    "Stub catalog queries are supported only in browse mode",
                    details={"node_id": node_id},
                )
            if node_id not in fixtures:
                raise UnknownNodeError(
                    f"node_id={node_id!r} not in stub fixtures",
                    details={"node_id": node_id, "namespace": reference["namespace"]},
                )
            payload = fixtures[node_id]

        return {
            "system": reference["system_code"],
            "ref": reference,
            "payload": payload,
            "fetched_at": pendulum.now("UTC").to_iso8601_string(),
            "ttl_seconds": ttl,
        }

    @staticmethod
    def _filter_fixtures(fixtures: dict, query: Optional[Any]) -> dict:
        if not query:
            return fixtures
        if not isinstance(query, dict) or not isinstance(query.get("match"), dict):
            raise SystemError(
                'Stub catalog query must have shape {"match": {"field": value}}'
            )
        match = query["match"]
        return {
            node_id: payload
            for node_id, payload in fixtures.items()
            if isinstance(payload, dict)
            and all(payload.get(field) == value for field, value in match.items())
        }

    @staticmethod
    def _extract_extra_config(config: Any) -> Any:
        """
        Read ``extra_config`` off either a PynamoDB model or a plain dict.

        PynamoDB ``MapAttribute`` values come back as a special object whose
        ``as_dict()`` returns a real dict; falling back to attribute access
        keeps the handler usable with plain-dict configs from tests.
        """
        if config is None:
            return {}
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
