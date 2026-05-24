#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Unit tests for Neo4j catalog and availability handlers.

All tests mock the ``neo4j.GraphDatabase`` driver by injecting a fake ``neo4j``
module into ``sys.modules`` before the handler's lazy import resolves. No real
Neo4j instance or driver installation is required.
"""
from __future__ import annotations

__author__ = "bibow"

import builtins
import importlib
import sys
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

import pytest


class FakeConfig:
    def __init__(
        self,
        *,
        adapter_id: Optional[str] = None,
        system_code: str = "neo4j",
        auth_strategy: str = "none",
        auth_secret_value: Optional[str] = None,
        auth_secret_ref: Optional[str] = None,
        endpoint_url: str = "bolt://localhost:7687",
        timeout_seconds: int = 30,
        cache_ttl_seconds: int = 300,
        extra_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.adapter_id = adapter_id
        self.system_code = system_code
        self.auth_strategy = auth_strategy
        self.auth_secret_value = auth_secret_value
        self.auth_secret_ref = auth_secret_ref
        self.endpoint_url = endpoint_url
        self.timeout_seconds = timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self.extra_config = extra_config or {}


@pytest.fixture
def info():
    return SimpleNamespace(context={"partition_key": "tenant-test"})


@pytest.fixture(autouse=True)
def isolated_registry():
    from ai_rfq_engine.handlers.catalog import clear_handlers
    from ai_rfq_engine.handlers.availability import clear_handlers as clear_avail

    clear_handlers()
    clear_avail()
    yield
    clear_handlers()
    clear_avail()


class _DictRecord(dict):
    """A dict that also supports attribute access so both dict(record) and record['key'] work."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _make_mock_driver(records=None, side_effect=None):
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_result = MagicMock()

    if side_effect is not None:
        mock_session.run.side_effect = side_effect
    else:
        mock_records = records or []
        dict_records = []
        for rec in mock_records:
            if isinstance(rec, dict):
                dict_records.append(_DictRecord(rec))
            else:
                dict_records.append(rec)
        mock_result.__iter__ = MagicMock(return_value=iter(dict_records))

    mock_session.run.return_value = mock_result
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_driver.session.return_value = mock_session
    return mock_driver


@pytest.fixture()
def mock_neo4j():
    """
    Install a fake ``neo4j`` module in ``sys.modules`` so the handler's
    ``from neo4j import GraphDatabase`` resolves to our mock.
    """
    mock_gdb = MagicMock()
    fake_neo4j = MagicMock()
    fake_neo4j.GraphDatabase = mock_gdb
    fake_neo4j.Query = MagicMock(side_effect=lambda text, timeout=None: text)
    mock_gdb.Query = fake_neo4j.Query
    prev = sys.modules.get("neo4j")
    sys.modules["neo4j"] = fake_neo4j
    yield mock_gdb
    if prev is None:
        sys.modules.pop("neo4j", None)
    else:
        sys.modules["neo4j"] = prev


# --- Neo4jCatalogHandler tests ---------------------------------------------- #


class TestNeo4jCatalogHandlerQueryBuilding:
    def test_default_node_cypher_when_no_custom_query(self):
        from ai_rfq_engine.handlers.catalog.neo4j_handler import Neo4jCatalogHandler

        handler = Neo4jCatalogHandler()
        ref = {"system_code": "neo4j", "namespace": "travel", "node_id": "hotel:001"}
        cypher, params = handler._build_query(ref, FakeConfig(), None, "travel")
        assert "$node_id" in cypher
        assert params["node_id"] == "hotel:001"

    def test_custom_cypher_from_extra_config(self):
        from ai_rfq_engine.handlers.catalog.neo4j_handler import Neo4jCatalogHandler

        handler = Neo4jCatalogHandler()
        ref = {"system_code": "neo4j", "namespace": "travel", "node_id": "hotel:001"}
        config = FakeConfig(
            extra_config={
                "cypher_query": "MATCH (h:Hotel {id: $node_id}) RETURN h",
                "query_parameters": {"depth": 2},
            }
        )
        cypher, params = handler._build_query(ref, config, None, "travel")
        assert cypher == "MATCH (h:Hotel {id: $node_id}) RETURN h"
        assert params["depth"] == 2
        assert params["node_id"] == "hotel:001"

    def test_browse_mode_uses_browse_cypher(self):
        from ai_rfq_engine.handlers.catalog.neo4j_handler import Neo4jCatalogHandler

        handler = Neo4jCatalogHandler()
        ref = {"system_code": "neo4j", "namespace": "travel", "node_id": None}
        cypher, params = handler._build_query(ref, FakeConfig(), None, "travel")
        assert "MATCH" in cypher
        assert params["node_id"] is None

    def test_auth_none_returns_none(self):
        from ai_rfq_engine.handlers.catalog.neo4j_handler import Neo4jCatalogHandler

        result = Neo4jCatalogHandler._build_auth(FakeConfig(auth_strategy="none"), None)
        assert result is None

    def test_auth_basic_with_credential(self):
        from ai_rfq_engine.handlers.catalog.neo4j_handler import Neo4jCatalogHandler

        result = Neo4jCatalogHandler._build_auth(
            FakeConfig(auth_strategy="basic"), "my-password"
        )
        assert result == ("neo4j", "my-password")

    def test_auth_uses_custom_username_from_extra_config(self):
        from ai_rfq_engine.handlers.catalog.neo4j_handler import Neo4jCatalogHandler

        result = Neo4jCatalogHandler._build_auth(
            FakeConfig(auth_strategy="basic", extra_config={"neo4j_username": "admin"}),
            "my-password",
        )
        assert result == ("admin", "my-password")

    def test_rejects_auth_strategy_not_supported_by_neo4j_handler(self):
        from ai_rfq_engine.handlers.catalog import CatalogSystemError
        from ai_rfq_engine.handlers.catalog.neo4j_handler import Neo4jCatalogHandler

        with pytest.raises(CatalogSystemError, match="does not support"):
            Neo4jCatalogHandler._build_auth(
                FakeConfig(auth_strategy="bearer_token"), "token"
            )


class TestNeo4jCatalogHandlerInquire:
    def test_inquire_returns_payload_for_known_node(self, mock_neo4j):
        from ai_rfq_engine.handlers.catalog.neo4j_handler import Neo4jCatalogHandler
        from ai_rfq_engine.handlers.catalog import register_handler

        mock_driver = _make_mock_driver(
            records=[{"n": {"name": "Tokyo Grand", "stars": 5}}]
        )
        mock_neo4j.driver.return_value = mock_driver

        register_handler("neo4j", Neo4jCatalogHandler)
        handler = Neo4jCatalogHandler()
        result = handler.inquire(
            reference={"system_code": "neo4j", "namespace": "travel", "node_id": "hotel:001"},
            config=FakeConfig(auth_strategy="none"),
            credential=None,
        )
        assert result["system"] == "neo4j"
        assert result["payload"]["properties"]["name"] == "Tokyo Grand"
        assert result["fetched_at"] is not None
        mock_neo4j.Query.assert_called_once_with(
            "MATCH (n {node_id: $node_id, namespace: $namespace}) RETURN n LIMIT 1",
            timeout=30.0,
        )
        mock_driver.close.assert_called_once()

    def test_inquire_raises_unknown_node_for_empty_result(self, mock_neo4j):
        from ai_rfq_engine.handlers.catalog.neo4j_handler import Neo4jCatalogHandler
        from ai_rfq_engine.handlers.catalog import UnknownNodeError, register_handler

        mock_driver = _make_mock_driver(records=[])
        mock_neo4j.driver.return_value = mock_driver

        register_handler("neo4j", Neo4jCatalogHandler)
        handler = Neo4jCatalogHandler()
        with pytest.raises(UnknownNodeError, match="hotel:missing"):
            handler.inquire(
                reference={"system_code": "neo4j", "namespace": "travel", "node_id": "hotel:missing"},
                config=FakeConfig(auth_strategy="none"),
                credential=None,
            )

    def test_inquire_raises_system_error_on_driver_failure(self, mock_neo4j):
        from ai_rfq_engine.handlers.catalog.neo4j_handler import Neo4jCatalogHandler
        from ai_rfq_engine.handlers.catalog import CatalogSystemError, register_handler

        mock_driver = MagicMock()
        mock_driver.session.side_effect = Exception("connection refused")
        mock_neo4j.driver.return_value = mock_driver

        register_handler("neo4j", Neo4jCatalogHandler)
        handler = Neo4jCatalogHandler()
        with pytest.raises(CatalogSystemError, match="connection refused"):
            handler.inquire(
                reference={"system_code": "neo4j", "namespace": "travel", "node_id": "x"},
                config=FakeConfig(auth_strategy="none"),
                credential=None,
            )

    def test_inquire_raises_timeout_error(self, mock_neo4j):
        from ai_rfq_engine.handlers.catalog.neo4j_handler import Neo4jCatalogHandler
        from ai_rfq_engine.handlers.catalog import SystemTimeoutError, register_handler

        mock_driver = MagicMock()
        mock_driver.session.side_effect = Exception("query timed out")
        mock_neo4j.driver.return_value = mock_driver

        register_handler("neo4j", Neo4jCatalogHandler)
        handler = Neo4jCatalogHandler()
        with pytest.raises(SystemTimeoutError):
            handler.inquire(
                reference={"system_code": "neo4j", "namespace": "travel", "node_id": "x"},
                config=FakeConfig(auth_strategy="none"),
                credential=None,
            )

    def test_inquire_raises_system_error_when_neo4j_not_installed(self, monkeypatch):
        from ai_rfq_engine.handlers.catalog.neo4j_handler import Neo4jCatalogHandler
        from ai_rfq_engine.handlers.catalog import CatalogSystemError, register_handler

        register_handler("neo4j", Neo4jCatalogHandler)
        handler = Neo4jCatalogHandler()

        real_import = builtins.__import__

        def import_without_neo4j(name, *args, **kwargs):
            if name == "neo4j":
                raise ImportError("neo4j unavailable for test")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", import_without_neo4j)
        with pytest.raises(CatalogSystemError, match="neo4j driver is not installed"):
            handler.inquire(
                reference={"system_code": "neo4j", "namespace": "travel", "node_id": "x"},
                config=FakeConfig(auth_strategy="none"),
                credential=None,
            )

    def test_browse_mode_returns_list_payload(self, mock_neo4j):
        from ai_rfq_engine.handlers.catalog.neo4j_handler import Neo4jCatalogHandler
        from ai_rfq_engine.handlers.catalog import register_handler

        mock_driver = _make_mock_driver(
            records=[
                {"n": {"name": "Hotel A"}},
                {"n": {"name": "Hotel B"}},
            ]
        )
        mock_neo4j.driver.return_value = mock_driver

        register_handler("neo4j", Neo4jCatalogHandler)
        handler = Neo4jCatalogHandler()
        result = handler.inquire(
            reference={"system_code": "neo4j", "namespace": "travel", "node_id": None},
            config=FakeConfig(auth_strategy="none"),
            credential=None,
        )
        assert isinstance(result["payload"], list)
        assert len(result["payload"]) == 2

    def test_uses_endpoint_url_from_config(self, mock_neo4j):
        from ai_rfq_engine.handlers.catalog.neo4j_handler import Neo4jCatalogHandler
        from ai_rfq_engine.handlers.catalog import register_handler

        mock_driver = _make_mock_driver(records=[{"n": {"name": "Test"}}])
        mock_neo4j.driver.return_value = mock_driver

        register_handler("neo4j", Neo4jCatalogHandler)
        handler = Neo4jCatalogHandler()
        handler.inquire(
            reference={"system_code": "neo4j", "namespace": "travel", "node_id": "x"},
            config=FakeConfig(auth_strategy="none", endpoint_url="bolt://prod:7687"),
            credential=None,
        )
        mock_neo4j.driver.assert_called_with("bolt://prod:7687", auth=None)


class TestNeo4jCatalogRegistration:
    def test_neo4j_handler_registered_on_import(self):
        import ai_rfq_engine.handlers.catalog as catalog_handlers

        importlib.reload(catalog_handlers)
        assert catalog_handlers.get_handler("neo4j") is catalog_handlers.Neo4jCatalogHandler

    def test_stub_and_neo4j_both_registered(self):
        from ai_rfq_engine.handlers.catalog import (
            StubCatalogHandler,
            Neo4jCatalogHandler,
            register_handler,
            registered_handlers,
        )

        register_handler("stub", StubCatalogHandler)
        register_handler("neo4j", Neo4jCatalogHandler)
        handlers = registered_handlers()
        assert "stub" in handlers
        assert "neo4j" in handlers


# --- Neo4jAvailabilityHandler tests ------------------------------------------ #


def _availability_config() -> FakeConfig:
    return FakeConfig(
        auth_strategy="none",
        extra_config={
            "check_cypher": "RETURN true AS available",
            "acquire_hold_cypher": "RETURN $hold_token AS hold_token, $expires_at AS expires_at",
            "release_hold_cypher": "RETURN true AS available, $hold_token AS hold_token",
            "confirm_hold_cypher": "RETURN true AS available, $hold_token AS hold_token",
        },
    )


class TestNeo4jAvailabilityHandler:
    def test_operation_requires_configured_capacity_cypher(self):
        from ai_rfq_engine.handlers.availability import OperationUnsupportedError
        from ai_rfq_engine.handlers.availability.neo4j_handler import Neo4jAvailabilityHandler

        with pytest.raises(OperationUnsupportedError, match="check_cypher"):
            Neo4jAvailabilityHandler().check(
                request={"provider_item_uuid": "room-1"},
                config=FakeConfig(auth_strategy="none"),
                credential=None,
            )

    def test_check_returns_available(self, mock_neo4j):
        from ai_rfq_engine.handlers.availability.neo4j_handler import Neo4jAvailabilityHandler
        from ai_rfq_engine.handlers.availability import register_handler

        mock_driver = _make_mock_driver(
            records=[{"available": True, "hold_token": None, "expires_at": None}]
        )
        mock_neo4j.driver.return_value = mock_driver

        register_handler("neo4j", Neo4jAvailabilityHandler)
        handler = Neo4jAvailabilityHandler()
        result = handler.check(
            request={"provider_item_uuid": "room-1"},
            config=_availability_config(),
            credential=None,
        )
        assert result["available"] is True
        assert result["operation"] == "check"
        assert result["hold_token"] is None

    def test_acquire_hold_returns_hold_token(self, mock_neo4j):
        from ai_rfq_engine.handlers.availability.neo4j_handler import Neo4jAvailabilityHandler
        from ai_rfq_engine.handlers.availability import register_handler

        mock_driver = _make_mock_driver(
            records=[{"hold_token": "hold-1", "expires_at": "2026-07-01T00:15:00Z"}]
        )
        mock_neo4j.driver.return_value = mock_driver

        register_handler("neo4j", Neo4jAvailabilityHandler)
        handler = Neo4jAvailabilityHandler()
        result = handler.acquire_hold(
            request={"provider_item_uuid": "room-1"},
            config=_availability_config(),
            credential=None,
        )
        assert result["operation"] == "acquire_hold"
        assert result["available"] is True
        assert result["hold_token"] == "hold-1"

    def test_acquire_hold_does_not_create_hold_when_capacity_is_unavailable(
        self, mock_neo4j
    ):
        from ai_rfq_engine.handlers.availability.neo4j_handler import Neo4jAvailabilityHandler

        mock_driver = _make_mock_driver(records=[])
        mock_neo4j.driver.return_value = mock_driver

        result = Neo4jAvailabilityHandler().acquire_hold(
            request={"provider_item_uuid": "room-1"},
            config=_availability_config(),
            credential=None,
        )
        assert result["available"] is False
        assert result["hold_token"] is None
        assert result["expires_at"] is None

    def test_release_hold_requires_hold_token(self):
        from ai_rfq_engine.handlers.availability.neo4j_handler import Neo4jAvailabilityHandler
        from ai_rfq_engine.handlers.availability import UnknownHoldError, register_handler

        register_handler("neo4j", Neo4jAvailabilityHandler)
        handler = Neo4jAvailabilityHandler()
        with pytest.raises(UnknownHoldError):
            handler.release_hold(
                request={"provider_item_uuid": "room-1"},
                config=_availability_config(),
                credential=None,
            )

    def test_confirm_hold_requires_hold_token(self):
        from ai_rfq_engine.handlers.availability.neo4j_handler import Neo4jAvailabilityHandler
        from ai_rfq_engine.handlers.availability import UnknownHoldError, register_handler

        register_handler("neo4j", Neo4jAvailabilityHandler)
        handler = Neo4jAvailabilityHandler()
        with pytest.raises(UnknownHoldError):
            handler.confirm_hold(
                request={"provider_item_uuid": "room-1"},
                config=_availability_config(),
                credential=None,
            )

    def test_release_hold_unknown_token_raises(self, mock_neo4j):
        from ai_rfq_engine.handlers.availability.neo4j_handler import Neo4jAvailabilityHandler
        from ai_rfq_engine.handlers.availability import UnknownHoldError, register_handler

        mock_driver = _make_mock_driver(records=[])
        mock_neo4j.driver.return_value = mock_driver

        register_handler("neo4j", Neo4jAvailabilityHandler)
        handler = Neo4jAvailabilityHandler()
        with pytest.raises(UnknownHoldError):
            handler.release_hold(
                request={"provider_item_uuid": "room-1", "hold_token": "bad-token"},
                config=_availability_config(),
                credential=None,
            )

    def test_confirm_hold_unknown_token_raises(self, mock_neo4j):
        from ai_rfq_engine.handlers.availability.neo4j_handler import Neo4jAvailabilityHandler
        from ai_rfq_engine.handlers.availability import UnknownHoldError, register_handler

        mock_driver = _make_mock_driver(records=[])
        mock_neo4j.driver.return_value = mock_driver

        register_handler("neo4j", Neo4jAvailabilityHandler)
        handler = Neo4jAvailabilityHandler()
        with pytest.raises(UnknownHoldError):
            handler.confirm_hold(
                request={"provider_item_uuid": "room-1", "hold_token": "bad-token"},
                config=_availability_config(),
                credential=None,
            )

    def test_auth_building_matches_catalog_handler(self):
        from ai_rfq_engine.handlers.availability.neo4j_handler import Neo4jAvailabilityHandler

        assert Neo4jAvailabilityHandler._build_auth(FakeConfig(auth_strategy="none"), None) is None
        result = Neo4jAvailabilityHandler._build_auth(
            FakeConfig(auth_strategy="basic", extra_config={"neo4j_username": "admin"}),
            "pw",
        )
        assert result == ("admin", "pw")

    def test_extract_extra_config_from_dict(self):
        from ai_rfq_engine.handlers.availability.neo4j_handler import Neo4jAvailabilityHandler

        config = FakeConfig(extra_config={"key": "value"})
        result = Neo4jAvailabilityHandler._extract_extra_config(config)
        assert result == {"key": "value"}

    def test_system_error_on_connection_failure(self, mock_neo4j):
        from ai_rfq_engine.handlers.availability.neo4j_handler import Neo4jAvailabilityHandler
        from ai_rfq_engine.handlers.availability import AvailabilitySystemError, register_handler

        mock_driver = MagicMock()
        mock_driver.session.side_effect = Exception("connection refused")
        mock_neo4j.driver.return_value = mock_driver

        register_handler("neo4j", Neo4jAvailabilityHandler)
        handler = Neo4jAvailabilityHandler()
        with pytest.raises(AvailabilitySystemError, match="connection refused"):
            handler.check(
                request={"provider_item_uuid": "room-1"},
                config=_availability_config(),
                credential=None,
            )

    def test_timeout_error_on_query_timeout(self, mock_neo4j):
        from ai_rfq_engine.handlers.availability.neo4j_handler import Neo4jAvailabilityHandler
        from ai_rfq_engine.handlers.availability import SystemTimeoutError, register_handler

        mock_driver = MagicMock()
        mock_driver.session.side_effect = Exception("transaction timed out")
        mock_neo4j.driver.return_value = mock_driver

        register_handler("neo4j", Neo4jAvailabilityHandler)
        handler = Neo4jAvailabilityHandler()
        with pytest.raises(SystemTimeoutError):
            handler.check(
                request={"provider_item_uuid": "room-1"},
                config=_availability_config(),
                credential=None,
            )

    def test_registration_in_availability_registry(self):
        import ai_rfq_engine.handlers.availability as availability_handlers

        importlib.reload(availability_handlers)
        assert (
            availability_handlers.get_handler("neo4j")
            is availability_handlers.Neo4jAvailabilityHandler
        )
