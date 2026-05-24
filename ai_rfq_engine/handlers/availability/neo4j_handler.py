#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Neo4j availability and hold handler (G3/G8).

Connects to a Neo4j graph database to check inventory availability, acquire,
release, and confirm temporary holds. Uses Cypher queries with parameterized
placeholders for safe substitution.

Configuration expectations mirror the catalog handler:
    - ``endpoint_url``: bolt:// or neo4j:// URI.
    - ``auth_strategy``: ``"none"`` or ``"basic"``.
    - ``extra_config.check_cypher``: optional Cypher for check
      (``availability_cypher`` is accepted as a compatibility alias).
    - ``extra_config.acquire_hold_cypher``: optional Cypher for hold creation.
    - ``extra_config.release_hold_cypher``: optional Cypher for hold release.
    - ``extra_config.confirm_hold_cypher``: optional Cypher for hold confirmation.
    - ``extra_config.query_parameters``: extra Cypher parameters merged in.
    - ``timeout_seconds``: driver transaction timeout.
    - ``cache_ttl_seconds``: forwarded as ``ttl_seconds`` in responses.
"""

from __future__ import annotations

__author__ = "bibow"

from typing import Any, Optional

import pendulum

from .base import (
    AvailabilityHandler,
    AvailabilityRequest,
    AvailabilityResponse,
    OperationUnsupportedError,
    SystemError,
    SystemTimeoutError,
    UnknownHoldError,
)

class Neo4jAvailabilityHandler(AvailabilityHandler):
    """
    Availability handler backed by a Neo4j graph database.

    Creates a short-lived driver per operation. Supports check, acquire_hold,
    release_hold, and confirm_hold operations via parameterized Cypher queries.
    """

    def check(
        self,
        *,
        request: AvailabilityRequest,
        config: Any,
        credential: Optional[str],
    ) -> AvailabilityResponse:
        return self._execute("check", request, config, credential)

    def acquire_hold(
        self,
        *,
        request: AvailabilityRequest,
        config: Any,
        credential: Optional[str],
    ) -> AvailabilityResponse:
        return self._execute("acquire_hold", request, config, credential)

    def release_hold(
        self,
        *,
        request: AvailabilityRequest,
        config: Any,
        credential: Optional[str],
    ) -> AvailabilityResponse:
        return self._execute("release_hold", request, config, credential)

    def confirm_hold(
        self,
        *,
        request: AvailabilityRequest,
        config: Any,
        credential: Optional[str],
    ) -> AvailabilityResponse:
        return self._execute("confirm_hold", request, config, credential)

    def _execute(
        self,
        operation: str,
        request: AvailabilityRequest,
        config: Any,
        credential: Optional[str],
    ) -> AvailabilityResponse:
        endpoint = getattr(config, "endpoint_url", None) or "bolt://localhost:7687"
        timeout = getattr(config, "timeout_seconds", None) or 30
        cache_ttl = getattr(config, "cache_ttl_seconds", None)
        system_code = getattr(config, "system_code", "neo4j")

        auth = self._build_auth(config, credential)

        extra_dict = self._extract_extra_config(config)
        cypher_key = f"{operation}_cypher"
        cypher = extra_dict.get(cypher_key)
        if operation == "check" and not cypher:
            cypher = extra_dict.get("availability_cypher")
        if not cypher:
            raise OperationUnsupportedError(
                f"Neo4j {operation} requires extra_config.{cypher_key}",
                details={"operation": operation, "config_key": cypher_key},
            )
        extra_params = extra_dict.get("query_parameters") or {}

        params: dict[str, Any] = dict(extra_params)
        params["provider_item_uuid"] = request.get("provider_item_uuid")
        params["batch_no"] = request.get("batch_no")
        params["service_start_at"] = str(request.get("service_start_at", ""))
        params["service_end_at"] = str(request.get("service_end_at", ""))
        params["pax_breakdown"] = request.get("pax_breakdown")
        params["qty"] = request.get("qty")

        if operation == "acquire_hold":
            import uuid
            hold_token = str(uuid.uuid4())
            params["hold_token"] = hold_token
            params["expires_at"] = pendulum.now("UTC").add(minutes=15).to_iso8601_string()

        if operation in ("release_hold", "confirm_hold"):
            hold_token = request.get("hold_token")
            if not hold_token:
                raise UnknownHoldError(
                    f"{operation} requires a hold_token",
                    details={"provider_item_uuid": request.get("provider_item_uuid")},
                )
            params["hold_token"] = hold_token

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
                    f"Neo4j {operation} timed out after {timeout}s",
                    details={"endpoint": endpoint, "operation": operation},
                ) from exc
            raise SystemError(
                f"Neo4j {operation} failed: {exc}",
                details={"endpoint": endpoint, "operation": operation},
            ) from exc
        finally:
            if driver is not None:
                try:
                    driver.close()
                except Exception:
                    pass

        available = False
        response_hold_token = None
        response_expires_at = None
        payload = None

        if records:
            payload = records[0]
            if operation == "check":
                available = bool(payload.get("available", False))
            elif operation == "acquire_hold":
                response_hold_token = payload.get("hold_token")
                response_expires_at = payload.get("expires_at") or payload.get(
                    "hold_expires_at"
                )
                available = bool(response_hold_token and response_expires_at)
            else:
                available = bool(payload.get("available", False))
                response_hold_token = request.get("hold_token")
                response_expires_at = payload.get("expires_at") or payload.get(
                    "hold_expires_at"
                )

        if operation in ("release_hold", "confirm_hold") and not records:
            raise UnknownHoldError(
                f"Hold not found for {operation}",
                details={"provider_item_uuid": request.get("provider_item_uuid"), "hold_token": request.get("hold_token")},
            )

        return {
            "system": system_code,
            "operation": operation,
            "request": request,
            "available": available,
            "hold_token": response_hold_token,
            "expires_at": response_expires_at,
            "fetched_at": pendulum.now("UTC").to_iso8601_string(),
            "ttl_seconds": cache_ttl,
            "payload": payload,
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
                as_dict_fn = getattr(extra, "as_dict", None)
                if callable(as_dict_fn):
                    try:
                        username = as_dict_fn().get("neo4j_username", "neo4j")
                    except Exception:
                        pass
        return (username, credential) if credential else None

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
