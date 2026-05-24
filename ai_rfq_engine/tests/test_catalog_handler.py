#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Unit tests for G7b catalog inquiry handlers.

Covers:
  - Handler registry (register / get / clear / type-check)
  - StubCatalogHandler payload return + UnknownNodeError
  - resolve_credential_for inline / external / missing modes
  - get_external_system_config_type strips auth_secret_value
  - dispatch_inquire: happy path, not_configured (no config), not_configured
    (no handler), auth_unavailable, credential pass-through
  - resolve_inquire_catalog GraphQL wrapper: success envelope, in-band error
    translation

All tests run without DynamoDB by monkeypatching
``resolve_external_system_model_for``. No network or AWS dependencies.
"""
from __future__ import annotations

__author__ = "bibow"

from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest


# --- Fixtures --------------------------------------------------------------- #


class FakeConfig:
    """
    Lightweight stand-in for ``ExternalSystemConfigModel`` used by the dispatch
    tests. Mirrors only the attributes the dispatcher and handlers read.
    """

    def __init__(
        self,
        *,
        adapter_id: Optional[str] = None,
        auth_strategy: str = "none",
        auth_secret_value: Optional[str] = None,
        auth_secret_ref: Optional[str] = None,
        endpoint_url: str = "https://stub.local",
        timeout_seconds: int = 30,
        cache_ttl_seconds: int = 300,
        extra_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.adapter_id = adapter_id
        self.auth_strategy = auth_strategy
        self.auth_secret_value = auth_secret_value
        self.auth_secret_ref = auth_secret_ref
        self.endpoint_url = endpoint_url
        self.timeout_seconds = timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self.extra_config = extra_config or {}


@pytest.fixture
def info():
    """Minimal ResolveInfo stand-in with a partition_key context."""
    return SimpleNamespace(context={"partition_key": "tenant-test"})


@pytest.fixture(autouse=True)
def isolated_registry():
    """
    Clear the catalog handler registry around each test so registrations from
    one test don't bleed into another. This is the documented test-only use of
    ``clear_handlers``.
    """
    from ai_rfq_engine.handlers.catalog import clear_handlers

    clear_handlers()
    yield
    clear_handlers()


# --- Registry tests --------------------------------------------------------- #


class TestRegistry:
    def test_register_and_get_returns_class(self):
        from ai_rfq_engine.handlers.catalog import (
            CatalogHandler,
            get_handler,
            register_handler,
        )

        class MyHandler(CatalogHandler):
            def inquire(self, **kwargs):
                return {}

        register_handler("my_system", MyHandler)
        assert get_handler("my_system") is MyHandler

    def test_get_unknown_returns_none(self):
        from ai_rfq_engine.handlers.catalog import get_handler

        assert get_handler("does_not_exist") is None

    def test_register_rejects_non_handler_class(self):
        from ai_rfq_engine.handlers.catalog import register_handler

        class NotAHandler:
            pass

        with pytest.raises(TypeError):
            register_handler("bogus", NotAHandler)

    def test_register_rejects_empty_adapter_id(self):
        from ai_rfq_engine.handlers.catalog import (
            CatalogHandler,
            register_handler,
        )

        class OkHandler(CatalogHandler):
            def inquire(self, **kwargs):
                return {}

        with pytest.raises(ValueError):
            register_handler("", OkHandler)


# --- StubCatalogHandler tests ---------------------------------------------- #


class TestStubCatalogHandler:
    def test_returns_payload_for_known_node(self):
        from ai_rfq_engine.handlers.catalog.stub_handler import StubCatalogHandler

        handler = StubCatalogHandler()
        config = FakeConfig(
            extra_config={
                "fixtures": {"hotel:tokyo:001": {"name": "Tokyo Hilton", "stars": 5}},
                "ttl_seconds": 60,
            }
        )
        result = handler.inquire(
            reference={
                "system_code": "stub",
                "namespace": "DEFAULT",
                "node_id": "hotel:tokyo:001",
            },
            config=config,
            credential=None,
        )
        assert result["system"] == "stub"
        assert result["payload"] == {"name": "Tokyo Hilton", "stars": 5}
        assert result["ttl_seconds"] == 60
        assert result["fetched_at"]  # ISO-8601 string is populated

    def test_raises_unknown_node_for_missing_id(self):
        from ai_rfq_engine.handlers.catalog import UnknownNodeError
        from ai_rfq_engine.handlers.catalog.stub_handler import StubCatalogHandler

        handler = StubCatalogHandler()
        config = FakeConfig(extra_config={"fixtures": {"hotel:001": {}}})
        with pytest.raises(UnknownNodeError):
            handler.inquire(
                reference={
                    "system_code": "stub",
                    "namespace": "DEFAULT",
                    "node_id": "hotel:missing",
                },
                config=config,
                credential=None,
            )

    def test_browse_mode_returns_full_fixtures(self):
        """node_id=None returns the whole fixtures dict (browse / search flow)."""
        from ai_rfq_engine.handlers.catalog.stub_handler import StubCatalogHandler

        handler = StubCatalogHandler()
        fixtures = {"a": {"x": 1}, "b": {"y": 2}}
        config = FakeConfig(extra_config={"fixtures": fixtures})
        result = handler.inquire(
            reference={"system_code": "stub", "namespace": "DEFAULT", "node_id": None},
            config=config,
            credential=None,
        )
        assert result["payload"] == fixtures

    def test_browse_mode_filters_fixtures_using_match_query(self):
        from ai_rfq_engine.handlers.catalog.stub_handler import StubCatalogHandler

        result = StubCatalogHandler().inquire(
            reference={"system_code": "stub", "namespace": "DEFAULT", "node_id": None},
            config=FakeConfig(
                extra_config={
                    "fixtures": {
                        "a": {"city": "Tokyo", "stars": 5},
                        "b": {"city": "Osaka", "stars": 5},
                    }
                }
            ),
            credential=None,
            query={"match": {"city": "Tokyo"}},
        )
        assert result["payload"] == {"a": {"city": "Tokyo", "stars": 5}}

    def test_rejects_unsupported_stub_query_shape(self):
        from ai_rfq_engine.handlers.catalog import CatalogSystemError
        from ai_rfq_engine.handlers.catalog.stub_handler import StubCatalogHandler

        with pytest.raises(CatalogSystemError, match="must have shape"):
            StubCatalogHandler().inquire(
                reference={"system_code": "stub", "namespace": "DEFAULT", "node_id": None},
                config=FakeConfig(extra_config={"fixtures": {}}),
                credential=None,
                query={"unknown": True},
            )


# --- Credential resolution tests ------------------------------------------- #


class TestResolveCredentialFor:
    def test_inline_value_is_allowed_only_when_explicitly_enabled(self, monkeypatch):
        from ai_rfq_engine.handlers.config import Config
        from ai_rfq_engine.models.external_system_config import resolve_credential_for

        config = FakeConfig(
            auth_secret_value="inline-secret",
            auth_secret_ref="arn:aws:secretsmanager:...:never-resolved",
        )
        assert resolve_credential_for(config) is None
        monkeypatch.setattr(Config, "ALLOW_INLINE_AUTH_SECRET_VALUE", True)
        assert resolve_credential_for(config) == "inline-secret"

    def test_external_ref_uses_registered_secret_resolver(self):
        from ai_rfq_engine.models.external_system_config import (
            register_secret_resolver,
            resolve_credential_for,
        )

        config = FakeConfig(
            auth_secret_value=None, auth_secret_ref="arn:aws:secretsmanager:..."
        )
        register_secret_resolver(lambda ref: f"resolved:{ref}")
        try:
            assert resolve_credential_for(config).startswith("resolved:")
        finally:
            register_secret_resolver(None)

    def test_no_credential_returns_none(self):
        from ai_rfq_engine.models.external_system_config import resolve_credential_for

        config = FakeConfig(auth_secret_value=None, auth_secret_ref=None)
        assert resolve_credential_for(config) is None


# --- Type-stripping invariant test ----------------------------------------- #


class TestTypeStripsAuthSecretValue:
    def test_auth_secret_value_never_reaches_graphql_type(self, info):
        """
        get_external_system_config_type must strip ``auth_secret_value`` so it
        cannot leak via any GraphQL output, regardless of what the model row
        contains.
        """
        from ai_rfq_engine.models.external_system_config import (
            get_external_system_config_type,
        )

        # Build a fake model row by attribute population, mirroring what
        # PynamoDB would produce. The type-builder reads
        # ``__dict__['attribute_values']`` so we mimic that surface.
        class FakeModel:
            pass

        model = FakeModel()
        model.__dict__["attribute_values"] = {
            "partition_key": "tenant",
            "config_uuid": "cfg-1",
            "system_code": "stub",
            "auth_strategy": "bearer_token",
            "auth_secret_value": "SHOULD-NOT-LEAK",
            "auth_secret_ref": None,
            "endpoint_url": "https://stub",
        }
        result = get_external_system_config_type(info, model)
        # The graphene ObjectType silently accepts unknown kwargs but should
        # not have populated the field with the secret. Inspecting the
        # underlying dict is the strict check:
        assert getattr(result, "auth_secret_value", None) is None


# --- dispatch_inquire tests ------------------------------------------------ #


class TestDispatchInquire:
    def test_happy_path_calls_handler_with_credential(self, info, monkeypatch):
        from ai_rfq_engine.handlers.catalog import (
            CatalogHandler,
            dispatch_inquire,
            register_handler,
        )
        from ai_rfq_engine.handlers.catalog import registry as catalog_registry
        from ai_rfq_engine.handlers.config import Config

        captured: Dict[str, Any] = {}
        monkeypatch.setattr(Config, "ALLOW_INLINE_AUTH_SECRET_VALUE", True)

        class CapturingHandler(CatalogHandler):
            def inquire(self, *, reference, config, credential, query=None):
                captured["reference"] = reference
                captured["credential"] = credential
                captured["query"] = query
                return {
                    "system": reference["system_code"],
                    "ref": reference,
                    "payload": {"ok": True},
                    "fetched_at": "2026-05-23T00:00:00+00:00",
                    "ttl_seconds": 30,
                }

        register_handler("neo4j", CapturingHandler)
        monkeypatch.setattr(
            catalog_registry,
            "resolve_external_system_model_for",
            lambda _info, **kw: FakeConfig(
                auth_strategy="bearer_token",
                auth_secret_value="real-token",
            ),
        )

        result = dispatch_inquire(
            info,
            system_code="neo4j",
            namespace="travel-prod",
            node_id="hotel:001",
            query={"depth": 1},
        )
        assert result["payload"] == {"ok": True}
        assert captured["credential"] == "real-token"
        assert captured["reference"] == {
            "system_code": "neo4j",
            "namespace": "travel-prod",
            "node_id": "hotel:001",
        }
        assert captured["query"] == {"depth": 1}

    def test_not_configured_when_no_config_row(self, info, monkeypatch):
        from ai_rfq_engine.handlers.catalog import (
            NotConfiguredError,
            dispatch_inquire,
        )
        from ai_rfq_engine.handlers.catalog import registry as catalog_registry

        monkeypatch.setattr(
            catalog_registry, "resolve_external_system_model_for", lambda _info, **kw: None
        )
        with pytest.raises(NotConfiguredError):
            dispatch_inquire(info, system_code="neo4j", namespace="DEFAULT")

    def test_not_configured_when_no_handler_registered(self, info, monkeypatch):
        from ai_rfq_engine.handlers.catalog import (
            NotConfiguredError,
            dispatch_inquire,
        )
        from ai_rfq_engine.handlers.catalog import registry as catalog_registry

        monkeypatch.setattr(
            catalog_registry,
            "resolve_external_system_model_for",
            lambda _info, **kw: FakeConfig(auth_strategy="none"),
        )
        # No handler registered (autouse fixture cleared the registry)
        with pytest.raises(NotConfiguredError):
            dispatch_inquire(info, system_code="unregistered", namespace="DEFAULT")

    def test_auth_unavailable_when_strategy_requires_credential(
        self, info, monkeypatch
    ):
        from ai_rfq_engine.handlers.catalog import (
            AuthUnavailableError,
            CatalogHandler,
            dispatch_inquire,
            register_handler,
        )
        from ai_rfq_engine.handlers.catalog import registry as catalog_registry

        class UnusedHandler(CatalogHandler):
            def inquire(self, **kwargs):  # pragma: no cover - must not run
                raise AssertionError("handler must not be invoked when auth fails")

        register_handler("neo4j", UnusedHandler)
        monkeypatch.setattr(
            catalog_registry,
            "resolve_external_system_model_for",
            lambda _info, **kw: FakeConfig(
                auth_strategy="bearer_token",
                auth_secret_value=None,
                auth_secret_ref=None,
            ),
        )
        with pytest.raises(AuthUnavailableError):
            dispatch_inquire(info, system_code="neo4j", namespace="DEFAULT")

    def test_adapter_id_override_takes_precedence_over_system_code(
        self, info, monkeypatch
    ):
        """A config row's adapter_id field, when set, picks the handler."""
        from ai_rfq_engine.handlers.catalog import (
            CatalogHandler,
            dispatch_inquire,
            register_handler,
        )
        from ai_rfq_engine.handlers.catalog import registry as catalog_registry

        class WrongHandler(CatalogHandler):
            def inquire(self, **kwargs):  # pragma: no cover
                raise AssertionError("Wrong handler picked")

        class RightHandler(CatalogHandler):
            def inquire(self, **kwargs):
                return {
                    "system": "neo4j",
                    "ref": {"system_code": "neo4j", "namespace": "ns", "node_id": "x"},
                    "payload": "picked",
                    "fetched_at": "2026-05-23T00:00:00+00:00",
                    "ttl_seconds": None,
                }

        register_handler("neo4j", WrongHandler)
        register_handler("neo4j_v2", RightHandler)
        monkeypatch.setattr(
            catalog_registry,
            "resolve_external_system_model_for",
            lambda _info, **kw: FakeConfig(
                adapter_id="neo4j_v2", auth_strategy="none"
            ),
        )

        result = dispatch_inquire(
            info, system_code="neo4j", namespace="ns", node_id="x"
        )
        assert result["payload"] == "picked"


# --- GraphQL wrapper tests ------------------------------------------------- #


class TestResolveInquireCatalog:
    def test_success_returns_envelope_fields(self, info, monkeypatch):
        from ai_rfq_engine.handlers.catalog import (
            CatalogHandler,
            register_handler,
        )
        from ai_rfq_engine.handlers.catalog import registry as catalog_registry
        from ai_rfq_engine.queries.catalog_inquiry import resolve_inquire_catalog

        class OkHandler(CatalogHandler):
            def inquire(self, *, reference, config, credential, query=None):
                return {
                    "system": "stub",
                    "ref": reference,
                    "payload": {"hello": "world"},
                    "fetched_at": "2026-05-23T12:34:56+00:00",
                    "ttl_seconds": 120,
                }

        register_handler("stub", OkHandler)
        monkeypatch.setattr(
            catalog_registry,
            "resolve_external_system_model_for",
            lambda _info, **kw: FakeConfig(auth_strategy="none"),
        )

        result = resolve_inquire_catalog(
            info,
            system_code="stub",
            namespace="DEFAULT",
            node_id="n1",
        )
        assert result.system == "stub"
        assert result.namespace == "DEFAULT"
        assert result.node_id == "n1"
        assert result.payload == {"hello": "world"}
        assert result.ttl_seconds == 120
        assert result.error_code is None
        assert result.error_message is None

    def test_handler_error_returned_inband_with_code(self, info, monkeypatch):
        from ai_rfq_engine.handlers.catalog import registry as catalog_registry
        from ai_rfq_engine.queries.catalog_inquiry import resolve_inquire_catalog

        # No handler registered + no config -> not_configured
        monkeypatch.setattr(
            catalog_registry, "resolve_external_system_model_for", lambda _info, **kw: None
        )
        result = resolve_inquire_catalog(
            info, system_code="missing", namespace="DEFAULT", node_id="n1"
        )
        assert result.error_code == "not_configured"
        assert result.error_message
        assert result.payload is None
        assert result.fetched_at is None
