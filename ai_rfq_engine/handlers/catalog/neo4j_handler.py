#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Neo4j catalog inquiry handler (G7b).

Connects to a Neo4j graph database using the official ``neo4j`` Python driver
and returns normalised ``CatalogResponse`` envelopes. The handler is registered
under the adapter id ``"neo4j"`` and is activated when an
``ExternalSystemConfigModel`` row has ``system_code='neo4j'`` (or an explicit
``adapter_id='neo4j'`` override).

Configuration expectations (from the ExternalSystemConfig row):
    - ``endpoint_url``: bolt:// or neo4j:// URI for the Neo4j server.
    - ``auth_strategy``: ``"none"`` for unauthenticated or ``"basic"`` for a
      username/password connection.
    - ``extra_config.cypher_query``: optional parameterized Cypher query.
      ``$node_id``, ``$namespace``, and ``$system_code`` are supplied as
      parameters. When omitted, a default node or browse query is used.
    - ``extra_config.query_parameters``: optional dict of extra Cypher
      parameters merged into every query.
    - ``timeout_seconds``: used as the Neo4j driver transaction timeout.
    - ``cache_ttl_seconds``: forwarded as ``ttl_seconds`` in the response.
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
    SystemTimeoutError,
    UnknownNodeError,
)

_DEFAULT_NODE_CYPHER = (
    "MATCH (n {node_id: $node_id, namespace: $namespace}) "
    "RETURN n LIMIT 1"
)
_DEFAULT_BROWSE_CYPHER = (
    "MATCH (n {namespace: $namespace}) "
    "RETURN n"
)


class Neo4jCatalogHandler(CatalogHandler):
    """
    Catalog handler backed by a Neo4j graph database.

    The handler creates a short-lived driver per ``inquire`` call (or can be
    overridden to pool via subclassing). The ``credential`` is used as the
    Neo4j auth password when ``auth_strategy`` is not ``"none"``.
    """

    def inquire(
        self,
        *,
        reference: CatalogReference,
        config: Any,
        credential: Optional[str],
        query: Optional[Any] = None,
    ) -> CatalogResponse:
        endpoint = getattr(config, "endpoint_url", None) or "bolt://localhost:7687"
        timeout = getattr(config, "timeout_seconds", None) or 30
        cache_ttl = getattr(config, "cache_ttl_seconds", None)
        namespace = reference["namespace"]

        auth = self._build_auth(config, credential)
        cypher, params = self._build_query(reference, config, query, namespace)

        try:
            from neo4j import GraphDatabase, Query
        except ImportError as exc:
            raise SystemError(
                "neo4j driver is not installed",
                details={"hint": "pip install neo4j"},
            ) from exc

        driver = None
        try:
            driver = GraphDatabase.driver(endpoint, auth=auth)
            with driver.session() as session:
                result = session.run(
                    Query(cypher, timeout=float(timeout)),
                    parameters=params,
                )
                records = [dict(record) for record in result]
        except Exception as exc:
            error_msg = str(exc).lower()
            if "timeout" in error_msg or "timed out" in error_msg:
                raise SystemTimeoutError(
                    f"Neo4j query timed out after {timeout}s",
                    details={"endpoint": endpoint, "node_id": reference.get("node_id")},
                ) from exc
            raise SystemError(
                f"Neo4j query failed: {exc}",
                details={"endpoint": endpoint, "node_id": reference.get("node_id")},
            ) from exc
        finally:
            if driver is not None:
                try:
                    driver.close()
                except Exception:
                    pass

        node_id = reference.get("node_id")
        if node_id is not None and not records:
            raise UnknownNodeError(
                f"node_id={node_id!r} not found in Neo4j",
                details={"node_id": node_id, "namespace": namespace},
            )

        payload: Any
        if node_id is not None:
            node_data = dict(records[0]["n"]) if records and "n" in records[0] else records[0] if records else {}
            payload = {"properties": node_data, "relationships": []}
        else:
            payload = [
                {"properties": dict(r["n"]), "relationships": []}
                if "n" in r else r
                for r in records
            ] if records else []

        return {
            "system": reference["system_code"],
            "ref": reference,
            "payload": payload,
            "fetched_at": pendulum.now("UTC").to_iso8601_string(),
            "ttl_seconds": cache_ttl,
        }

    @staticmethod
    def _build_auth(config: Any, credential: Optional[str]):
        auth_strategy = (getattr(config, "auth_strategy", None) or "none").lower()
        if auth_strategy == "none":
            return None
        if auth_strategy != "basic":
            raise SystemError(
                f"Neo4j handler does not support auth_strategy={auth_strategy!r}",
                details={"auth_strategy": auth_strategy},
            )
        username = "neo4j"
        extra = getattr(config, "extra_config", None)
        if extra is not None:
            if isinstance(extra, dict):
                username = extra.get("neo4j_username", "neo4j")
            else:
                as_dict = getattr(extra, "as_dict", None)
                if callable(as_dict):
                    try:
                        username = as_dict().get("neo4j_username", "neo4j")
                    except Exception:
                        pass
        return (username, credential) if credential else None

    @staticmethod
    def _build_query(
        reference: CatalogReference,
        config: Any,
        query: Optional[Any],
        namespace: str,
    ) -> tuple[str, dict[str, Any]]:
        node_id = reference.get("node_id")

        extra = getattr(config, "extra_config", None)
        if extra is not None:
            if isinstance(extra, dict):
                extra_dict = extra
            else:
                as_dict = getattr(extra, "as_dict", None)
                if callable(as_dict):
                    try:
                        extra_dict = as_dict()
                    except Exception:
                        extra_dict = {}
                else:
                    extra_dict = {}
        else:
            extra_dict = {}

        cypher = extra_dict.get("cypher_query")
        extra_params = extra_dict.get("query_parameters") or {}

        params: dict[str, Any] = dict(extra_params)
        params["node_id"] = node_id
        params["namespace"] = namespace
        params["system_code"] = reference.get("system_code", "neo4j")

        if query and isinstance(query, dict):
            query_params = query.get("parameters")
            if isinstance(query_params, dict):
                params.update(query_params)

        params["node_id"] = node_id
        params["namespace"] = namespace
        params["system_code"] = reference.get("system_code", "neo4j")

        if node_id is not None:
            if not cypher:
                cypher = _DEFAULT_NODE_CYPHER
        elif not cypher:
            cypher = _DEFAULT_BROWSE_CYPHER

        return cypher, params
