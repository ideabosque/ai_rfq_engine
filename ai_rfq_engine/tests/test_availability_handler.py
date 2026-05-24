#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Unit tests for G3 availability dispatch and quote-item enforcement."""
from __future__ import annotations

__author__ = "bibow"

from types import SimpleNamespace

import pendulum
import pytest


class FakeConfig:
    def __init__(
        self,
        *,
        adapter_id=None,
        system_code="stub",
        auth_strategy="none",
        auth_secret_value=None,
        extra_config=None,
    ):
        self.adapter_id = adapter_id
        self.system_code = system_code
        self.auth_strategy = auth_strategy
        self.auth_secret_value = auth_secret_value
        self.auth_secret_ref = None
        self.extra_config = extra_config or {}


@pytest.fixture
def info():
    return SimpleNamespace(context={"partition_key": "tenant-test"})


@pytest.fixture(autouse=True)
def isolated_registry():
    from ai_rfq_engine.handlers.availability import clear_handlers

    clear_handlers()
    yield
    clear_handlers()


@pytest.mark.unit
def test_stub_check_is_read_only_and_acquire_returns_hold():
    from ai_rfq_engine.handlers.availability.stub_handler import (
        StubAvailabilityHandler,
    )

    config = FakeConfig(
        extra_config={
            "fixtures": {
                "room-1#night-1": {
                    "available": True,
                    "hold_token": "hold-1",
                    "expires_at": "2026-06-01T00:15:00Z",
                }
            },
            "ttl_seconds": 30,
        }
    )
    handler = StubAvailabilityHandler()
    request = {
        "provider_item_uuid": "room-1",
        "batch_no": "night-1",
        "service_start_at": pendulum.datetime(2026, 6, 1, tz="UTC"),
        "service_end_at": pendulum.datetime(2026, 6, 2, tz="UTC"),
    }
    result = handler.check(
        request=request,
        config=config,
        credential=None,
    )
    held = handler.acquire_hold(
        request=request,
        config=config,
        credential=None,
    )
    assert result["available"] is True
    assert result["hold_token"] is None
    assert held["hold_token"] == "hold-1"
    assert held["operation"] == "acquire_hold"
    assert result["ttl_seconds"] == 30


@pytest.mark.unit
def test_stub_does_not_acquire_a_hold_for_unavailable_inventory():
    from ai_rfq_engine.handlers.availability import UnknownHoldError
    from ai_rfq_engine.handlers.availability.stub_handler import (
        StubAvailabilityHandler,
    )

    handler = StubAvailabilityHandler()
    config = FakeConfig(
        extra_config={
            "fixtures": {
                "room-1": {
                    "available": False,
                    "hold_token": "must-not-be-returned",
                }
            }
        }
    )
    result = handler.acquire_hold(
        request={"provider_item_uuid": "room-1"},
        config=config,
        credential=None,
    )
    assert result["available"] is False
    assert result["hold_token"] is None
    with pytest.raises(UnknownHoldError):
        handler.confirm_hold(
            request={"provider_item_uuid": "room-1", "hold_token": "must-not-be-returned"},
            config=config,
            credential=None,
        )


@pytest.mark.unit
def test_stub_release_and_confirm_require_the_acquired_token():
    from ai_rfq_engine.handlers.availability import UnknownHoldError
    from ai_rfq_engine.handlers.availability.stub_handler import (
        StubAvailabilityHandler,
    )

    handler = StubAvailabilityHandler()
    config = FakeConfig(
        extra_config={
            "fixtures": {
                "room-1": {
                    "available": True,
                    "hold_token": "hold-1",
                    "expires_at": "2026-06-01T00:15:00Z",
                }
            }
        }
    )
    with pytest.raises(UnknownHoldError):
        handler.release_hold(
            request={"provider_item_uuid": "room-1", "hold_token": "wrong"},
            config=config,
            credential=None,
        )
    result = handler.confirm_hold(
        request={"provider_item_uuid": "room-1", "hold_token": "hold-1"},
        config=config,
        credential=None,
    )
    assert result["operation"] == "confirm_hold"
    assert result["hold_token"] == "hold-1"


@pytest.mark.unit
def test_dispatch_check_resolves_availability_configuration(info, monkeypatch):
    from ai_rfq_engine.handlers.availability import (
        dispatch_check,
        register_handler,
    )
    from ai_rfq_engine.handlers.availability import registry
    from ai_rfq_engine.handlers.availability.stub_handler import (
        StubAvailabilityHandler,
    )

    register_handler("stub", StubAvailabilityHandler)
    monkeypatch.setattr(
        registry,
        "resolve_external_system_model_for",
        lambda _info, **kwargs: FakeConfig(
            adapter_id="stub",
            system_code="pms",
            extra_config={"fixtures": {"room-1": {"available": True}}}
        ),
    )
    result = dispatch_check(
        info,
        system_code="pms",
        provider_item_uuid="room-1",
        service_start_at=pendulum.datetime(2026, 6, 1, tz="UTC"),
        service_end_at=pendulum.datetime(2026, 6, 2, tz="UTC"),
    )
    assert result["available"] is True


class FakeSavedQuoteItem:
    captured = None

    def __init__(self, quote_uuid, quote_item_uuid, **cols):
        FakeSavedQuoteItem.captured = cols

    def save(self):
        return None


def _patch_quote_creation(monkeypatch):
    from ai_rfq_engine.models import item as item_model
    from ai_rfq_engine.models import quote as quote_model
    from ai_rfq_engine.models import quote_item as quote_item_model
    from ai_rfq_engine.models import provider_item as provider_item_model

    FakeSavedQuoteItem.captured = None
    monkeypatch.setattr(
        item_model, "get_item", lambda *args: SimpleNamespace(pricing_mode="unit")
    )
    monkeypatch.setattr(
        quote_model,
        "get_quote",
        lambda *args: SimpleNamespace(provider_corp_external_id="hotel-1"),
    )
    monkeypatch.setattr(
        provider_item_model,
        "get_provider_item",
        lambda *args: SimpleNamespace(
            availability_mode="require_hold",
            availability_system_code="pms",
            availability_namespace="DEFAULT",
            provider_corp_external_id="hotel-1",
        ),
    )
    monkeypatch.setattr(quote_model, "update_quote_totals", lambda *args: None)
    monkeypatch.setattr(quote_item_model, "QuoteItemModel", FakeSavedQuoteItem)
    monkeypatch.setattr(
        quote_item_model, "get_price_per_uom", lambda *args, **kwargs: 100.0
    )
    return quote_item_model.insert_update_quote_item.__wrapped__.__wrapped__


def _quote_kwargs():
    return {
        "entity": None,
        "quote_uuid": "quote",
        "quote_item_uuid": "line",
        "request_uuid": "request",
        "item_uuid": "item",
        "provider_item_uuid": "room-1",
        "segment_uuid": "segment",
        "qty": 1,
        "service_start_at": pendulum.datetime(2026, 6, 1, tz="UTC"),
        "service_end_at": pendulum.datetime(2026, 6, 2, tz="UTC"),
        "updated_by": "test",
    }


@pytest.mark.unit
def test_quote_creation_persists_availability_hold(info, monkeypatch):
    from ai_rfq_engine.handlers import availability

    raw_insert = _patch_quote_creation(monkeypatch)
    monkeypatch.setattr(
        availability,
        "dispatch_acquire_hold",
        lambda *args, **kwargs: {
            "available": True,
            "hold_token": "hold-1",
            "expires_at": "2026-06-01T00:15:00Z",
        },
    )
    raw_insert(info, **_quote_kwargs())
    assert FakeSavedQuoteItem.captured["hold_token"] == "hold-1"
    assert FakeSavedQuoteItem.captured["hold_expires_at"] == pendulum.parse(
        "2026-06-01T00:15:00Z"
    )


@pytest.mark.unit
def test_quote_creation_rejects_unavailable_capacity_before_save(info, monkeypatch):
    from ai_rfq_engine.handlers import availability

    raw_insert = _patch_quote_creation(monkeypatch)
    monkeypatch.setattr(
        availability,
        "dispatch_acquire_hold",
        lambda *args, **kwargs: {"available": False},
    )
    with pytest.raises(ValueError, match="not available"):
        raw_insert(info, **_quote_kwargs())
    assert FakeSavedQuoteItem.captured is None


@pytest.mark.unit
def test_quote_item_release_uses_server_owned_hold_context(info, monkeypatch):
    from ai_rfq_engine.handlers import availability
    from ai_rfq_engine.models import provider_item as provider_item_model
    from ai_rfq_engine.models.quote_item import _release_availability_hold

    calls = []
    monkeypatch.setattr(
        provider_item_model,
        "get_provider_item",
        lambda *args: SimpleNamespace(
            availability_mode="require_hold",
            availability_system_code="pms",
            availability_namespace="DEFAULT",
            provider_corp_external_id="hotel-1",
        ),
    )
    monkeypatch.setattr(
        availability, "dispatch_release_hold", lambda *args, **kwargs: calls.append(kwargs)
    )
    _release_availability_hold(
        info,
        SimpleNamespace(
            partition_key="tenant-test",
            provider_item_uuid="room-1",
            batch_no="night-1",
            hold_token="hold-1",
        ),
    )
    assert calls[0]["hold_token"] == "hold-1"
    assert calls[0]["system_code"] == "pms"


@pytest.mark.unit
def test_quote_acceptance_confirms_held_inventory(info, monkeypatch):
    from ai_rfq_engine.handlers import availability
    from ai_rfq_engine.models import provider_item as provider_item_model
    from ai_rfq_engine.models import quote_item as quote_item_model
    from ai_rfq_engine.models.quote import _confirm_quote_item_holds

    calls = []
    monkeypatch.setattr(
        quote_item_model,
        "get_quote_items_by_quote",
        lambda *args: [
            SimpleNamespace(
                partition_key="tenant-test",
                provider_item_uuid="room-1",
                batch_no="night-1",
                hold_token="hold-1",
            )
        ],
    )
    monkeypatch.setattr(
        provider_item_model,
        "get_provider_item",
        lambda *args: SimpleNamespace(
            availability_mode="require_hold",
            availability_system_code="pms",
            availability_namespace="DEFAULT",
            provider_corp_external_id="hotel-1",
        ),
    )
    monkeypatch.setattr(
        availability, "dispatch_confirm_hold", lambda *args, **kwargs: calls.append(kwargs)
    )
    _confirm_quote_item_holds(info, SimpleNamespace(quote_uuid="quote-1"))
    assert calls[0]["hold_token"] == "hold-1"
    assert calls[0]["provider_item_uuid"] == "room-1"


@pytest.mark.unit
def test_check_availability_query_returns_structured_error(info, monkeypatch):
    from ai_rfq_engine.handlers.availability import NotConfiguredError
    from ai_rfq_engine.queries import availability as availability_query

    monkeypatch.setattr(
        availability_query,
        "dispatch_check",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            NotConfiguredError("No active availability configuration")
        ),
    )
    result = availability_query.resolve_check_availability(
        info,
        system_code="pms",
        provider_item_uuid="room-1",
        service_start_at=pendulum.datetime(2026, 6, 1, tz="UTC"),
        service_end_at=pendulum.datetime(2026, 6, 2, tz="UTC"),
    )
    assert result.error_code == "not_configured"
    assert result.available is None
