#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Unit tests for availability enforcement in the quote workflow."""
from __future__ import annotations

__author__ = "bibow"

from types import SimpleNamespace
from unittest.mock import MagicMock

import pendulum
import pytest


@pytest.fixture
def info():
    return SimpleNamespace(
        context={
            "partition_key": "tenant-test",
            "endpoint_id": "test-endpoint",
        }
    )


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
        lambda *args: SimpleNamespace(availability_mode="require_hold"),
    )
    monkeypatch.setattr(quote_model, "update_quote_totals", lambda *args: None)
    monkeypatch.setattr(quote_item_model, "QuoteItemModel", FakeSavedQuoteItem)
    monkeypatch.setattr(
        quote_item_model, "get_price_per_uom", lambda *args, **kwargs: 100.0
    )
    monkeypatch.setattr(
        quote_item_model, "_enforce_availability", lambda *args, **kwargs: {
            "available": True,
            "hold_token": "hold-1",
            "expires_at": "2026-06-01T00:15:00Z",
        }
    )
    monkeypatch.setattr(
        quote_item_model, "_build_cancellation_snapshot", lambda *args, **kwargs: None
    )
    return quote_item_model.insert_update_quote_item.__wrapped__.__wrapped__


def _make_batch(
    service_start, service_end, in_stock=True, slow_move=False, availability_qty=None
):
    return SimpleNamespace(
        batch_no="BATCH-001",
        service_start_at=service_start,
        service_end_at=service_end,
        in_stock=in_stock,
        availability_qty=availability_qty,
        slow_move_item=slow_move,
        cost_per_uom=80.0,
        freight_cost_per_uom=10.0,
        additional_cost_per_uom=5.0,
    )


def _patch_batches(monkeypatch, batches):
    from ai_rfq_engine.models import provider_item_batches as batch_model

    fake_list = SimpleNamespace(
        provider_item_batch_list=batches, total=len(batches)
    )
    monkeypatch.setattr(
        batch_model, "resolve_provider_item_batch_list", lambda *a, **kw: fake_list
    )


def _patch_reservation_write(monkeypatch, result=None):
    from ai_rfq_engine.handlers.availability import handler

    if result is None:
        result = SimpleNamespace(status="held")
    monkeypatch.setattr(handler, "_reserve_capacity_for_hold", lambda *a, **kw: result)


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


class TestCheckAvailability:
    @pytest.mark.unit
    def test_check_returns_available_when_matching_in_stock_batches(
        self, info, monkeypatch
    ):
        from ai_rfq_engine.handlers.availability import dispatch_check

        _patch_batches(
            monkeypatch,
            [_make_batch(pendulum.datetime(2026, 5, 30, tz="UTC"),
                        pendulum.datetime(2026, 6, 5, tz="UTC"))],
        )
        result = dispatch_check(
            info,
            provider_item_uuid="room-1",
            service_start_at=pendulum.datetime(2026, 6, 1, tz="UTC"),
            service_end_at=pendulum.datetime(2026, 6, 2, tz="UTC"),
        )
        assert result["available"] is True
        assert result["operation"] == "check"
        assert result["payload"]["reason"] == "available"

    @pytest.mark.unit
    def test_check_returns_unavailable_when_no_matching_batches(
        self, info, monkeypatch
    ):
        from ai_rfq_engine.handlers.availability import dispatch_check

        _patch_batches(monkeypatch, [])
        result = dispatch_check(
            info,
            provider_item_uuid="room-1",
            service_start_at=pendulum.datetime(2026, 6, 1, tz="UTC"),
            service_end_at=pendulum.datetime(2026, 6, 2, tz="UTC"),
        )
        assert result["available"] is False
        assert result["payload"]["reason"] == "no_matching_batches"

    @pytest.mark.unit
    def test_check_returns_unavailable_when_all_batches_out_of_stock(
        self, info, monkeypatch
    ):
        from ai_rfq_engine.handlers.availability import dispatch_check

        _patch_batches(
            monkeypatch,
            [_make_batch(pendulum.datetime(2026, 5, 30, tz="UTC"),
                        pendulum.datetime(2026, 6, 5, tz="UTC"),
                        in_stock=False)],
        )
        result = dispatch_check(
            info,
            provider_item_uuid="room-1",
            service_start_at=pendulum.datetime(2026, 6, 1, tz="UTC"),
            service_end_at=pendulum.datetime(2026, 6, 2, tz="UTC"),
        )
        assert result["available"] is False
        assert result["payload"]["reason"] == "all_batches_out_of_stock"

    @pytest.mark.unit
    def test_check_returns_unavailable_when_requested_qty_exceeds_capacity(
        self, info, monkeypatch
    ):
        from ai_rfq_engine.handlers.availability import dispatch_check

        _patch_batches(
            monkeypatch,
            [
                _make_batch(
                    pendulum.datetime(2026, 5, 30, tz="UTC"),
                    pendulum.datetime(2026, 6, 5, tz="UTC"),
                    availability_qty=2,
                )
            ],
        )
        result = dispatch_check(
            info,
            provider_item_uuid="room-1",
            service_start_at=pendulum.datetime(2026, 6, 1, tz="UTC"),
            service_end_at=pendulum.datetime(2026, 6, 2, tz="UTC"),
            qty=3,
        )
        assert result["available"] is False
        assert result["payload"]["reason"] == "insufficient_availability"

    @pytest.mark.unit
    def test_check_rejects_nonpositive_requested_qty(self, info):
        from ai_rfq_engine.handlers.availability import dispatch_check

        with pytest.raises(ValueError, match="qty must be greater than 0"):
            dispatch_check(info, provider_item_uuid="room-1", qty=0)


class TestAcquireHold:
    @pytest.mark.unit
    def test_acquire_hold_returns_token_when_available(
        self, info, monkeypatch
    ):
        from ai_rfq_engine.handlers.availability import dispatch_acquire_hold

        _patch_reservation_write(monkeypatch)
        _patch_batches(
            monkeypatch,
            [_make_batch(pendulum.datetime(2026, 5, 30, tz="UTC"),
                        pendulum.datetime(2026, 6, 5, tz="UTC"),
                        availability_qty=2)],
        )
        result = dispatch_acquire_hold(
            info,
            provider_item_uuid="room-1",
            service_start_at=pendulum.datetime(2026, 6, 1, tz="UTC"),
            service_end_at=pendulum.datetime(2026, 6, 2, tz="UTC"),
            qty=1,
        )
        assert result["available"] is True
        assert result["hold_token"] is not None
        assert result["expires_at"] is not None
        assert result["payload"]["reason"] == "hold_acquired"

    @pytest.mark.unit
    def test_acquire_hold_rejects_when_all_out_of_stock(
        self, info, monkeypatch
    ):
        from ai_rfq_engine.handlers.availability import dispatch_acquire_hold

        _patch_batches(
            monkeypatch,
            [_make_batch(pendulum.datetime(2026, 5, 30, tz="UTC"),
                        pendulum.datetime(2026, 6, 5, tz="UTC"),
                        in_stock=False, availability_qty=2)],
        )
        result = dispatch_acquire_hold(
            info,
            provider_item_uuid="room-1",
            service_start_at=pendulum.datetime(2026, 6, 1, tz="UTC"),
            service_end_at=pendulum.datetime(2026, 6, 2, tz="UTC"),
            qty=1,
        )
        assert result["available"] is False
        assert result["hold_token"] is None

    @pytest.mark.unit
    def test_acquire_hold_raises_when_no_service_window(self, info):
        from ai_rfq_engine.handlers.availability import dispatch_acquire_hold

        with pytest.raises(ValueError, match="service_start_at and service_end_at are required"):
            dispatch_acquire_hold(
                info,
                provider_item_uuid="room-1",
            )

    @pytest.mark.unit
    def test_acquire_hold_rejects_nonpositive_requested_qty(self, info):
        from ai_rfq_engine.handlers.availability import dispatch_acquire_hold

        with pytest.raises(ValueError, match="qty must be greater than 0"):
            dispatch_acquire_hold(
                info,
                provider_item_uuid="room-1",
                service_start_at=pendulum.datetime(2026, 6, 1, tz="UTC"),
                service_end_at=pendulum.datetime(2026, 6, 2, tz="UTC"),
                qty=-1,
            )

    @pytest.mark.unit
    def test_acquire_hold_rejects_unquantified_local_capacity(self, info, monkeypatch):
        from ai_rfq_engine.handlers.availability import dispatch_acquire_hold

        _patch_batches(
            monkeypatch,
            [_make_batch(
                pendulum.datetime(2026, 5, 30, tz="UTC"),
                pendulum.datetime(2026, 6, 5, tz="UTC"),
            )],
        )
        result = dispatch_acquire_hold(
            info,
            provider_item_uuid="room-1",
            service_start_at=pendulum.datetime(2026, 6, 1, tz="UTC"),
            service_end_at=pendulum.datetime(2026, 6, 2, tz="UTC"),
            qty=1,
        )
        assert result["available"] is False
        assert result["payload"]["reason"] == "unquantified_capacity"

    @pytest.mark.unit
    def test_acquire_hold_fails_closed_when_atomic_reservation_loses_race(
        self, info, monkeypatch
    ):
        from ai_rfq_engine.handlers.availability import dispatch_acquire_hold
        from ai_rfq_engine.handlers.availability import handler

        _patch_batches(
            monkeypatch,
            [_make_batch(
                pendulum.datetime(2026, 5, 30, tz="UTC"),
                pendulum.datetime(2026, 6, 5, tz="UTC"),
                availability_qty=1,
            )],
        )
        monkeypatch.setattr(
            handler, "_reserve_capacity_for_hold", lambda *a, **kw: None
        )
        result = dispatch_acquire_hold(
            info,
            provider_item_uuid="room-1",
            service_start_at=pendulum.datetime(2026, 6, 1, tz="UTC"),
            service_end_at=pendulum.datetime(2026, 6, 2, tz="UTC"),
            qty=1,
        )
        assert result["available"] is False
        assert result["payload"]["reason"] == "insufficient_availability"


class TestReleaseAndConfirmHold:
    @pytest.mark.unit
    def test_release_hold_succeeds(self, info, monkeypatch):
        from ai_rfq_engine.handlers.availability import dispatch_release_hold
        from ai_rfq_engine.handlers.availability import handler

        hold = SimpleNamespace(
            provider_item_uuid="room-1", batch_no="BATCH-001", status="held"
        )
        transitions = []
        monkeypatch.setattr(handler, "_get_hold", lambda *args: hold)
        monkeypatch.setattr(
            handler,
            "_restore_stored_hold",
            lambda *args: transitions.append(args[2]),
        )

        result = dispatch_release_hold(
            info,
            provider_item_uuid="room-1",
            hold_token="hold-1",
        )
        assert result["operation"] == "release_hold"
        assert result["payload"]["reason"] == "hold_released"
        assert transitions == ["released"]

    @pytest.mark.unit
    def test_confirm_hold_succeeds(self, info, monkeypatch):
        from ai_rfq_engine.handlers.availability import dispatch_confirm_hold
        from ai_rfq_engine.handlers.availability import handler

        hold = SimpleNamespace(provider_item_uuid="room-1", batch_no="BATCH-001")
        confirmed = []
        monkeypatch.setattr(handler, "_get_hold", lambda *args: hold)
        monkeypatch.setattr(
            handler, "_confirm_stored_hold", lambda *args: confirmed.append(args[1])
        )

        result = dispatch_confirm_hold(
            info,
            provider_item_uuid="room-1",
            hold_token="hold-1",
        )
        assert result["operation"] == "confirm_hold"
        assert result["payload"]["reason"] == "hold_confirmed"
        assert confirmed == [hold]

    @pytest.mark.unit
    def test_release_hold_requires_token(self, info):
        from ai_rfq_engine.handlers.availability import dispatch_release_hold

        with pytest.raises(ValueError, match="hold_token is required"):
            dispatch_release_hold(
                info,
                provider_item_uuid="room-1",
            )

    @pytest.mark.unit
    def test_confirm_hold_requires_token(self, info):
        from ai_rfq_engine.handlers.availability import dispatch_confirm_hold

        with pytest.raises(ValueError, match="hold_token is required"):
            dispatch_confirm_hold(
                info,
                provider_item_uuid="room-1",
            )

    @pytest.mark.unit
    def test_expire_hold_restores_expired_capacity(self, info, monkeypatch):
        from ai_rfq_engine.handlers.availability import dispatch_expire_hold
        from ai_rfq_engine.handlers.availability import handler

        hold = SimpleNamespace(
            provider_item_uuid="room-1",
            batch_no="BATCH-001",
            status="held",
            expires_at=pendulum.now("UTC").subtract(minutes=1),
        )
        transitions = []
        monkeypatch.setattr(handler, "_get_hold", lambda *args: hold)
        monkeypatch.setattr(
            handler,
            "_restore_stored_hold",
            lambda *args: transitions.append(args[2]),
        )
        result = dispatch_expire_hold(
            info, provider_item_uuid="room-1", hold_token="hold-1"
        )
        assert result["operation"] == "expire_hold"
        assert result["payload"]["reason"] == "hold_expired"
        assert transitions == ["expired"]

    @pytest.mark.unit
    def test_released_hold_cannot_be_expired(self, info, monkeypatch):
        from ai_rfq_engine.handlers.availability import UnknownHoldError
        from ai_rfq_engine.handlers.availability import dispatch_expire_hold
        from ai_rfq_engine.handlers.availability import handler

        hold = SimpleNamespace(
            provider_item_uuid="room-1",
            batch_no="BATCH-001",
            status="released",
            expires_at=pendulum.now("UTC").subtract(minutes=1),
        )
        monkeypatch.setattr(handler, "_get_hold", lambda *args: hold)
        with pytest.raises(UnknownHoldError, match="already released"):
            dispatch_expire_hold(
                info, provider_item_uuid="room-1", hold_token="hold-1"
            )

    @pytest.mark.unit
    def test_expired_hold_cannot_be_released(self, info, monkeypatch):
        from ai_rfq_engine.handlers.availability import UnknownHoldError
        from ai_rfq_engine.handlers.availability import dispatch_release_hold
        from ai_rfq_engine.handlers.availability import handler

        hold = SimpleNamespace(
            provider_item_uuid="room-1",
            batch_no="BATCH-001",
            status="expired",
        )
        monkeypatch.setattr(handler, "_get_hold", lambda *args: hold)
        with pytest.raises(UnknownHoldError, match="has expired"):
            dispatch_release_hold(
                info, provider_item_uuid="room-1", hold_token="hold-1"
            )


class TestQuoteCreationWithAvailability:
    @pytest.mark.unit
    def test_quote_creation_persists_availability_hold(self, info, monkeypatch):
        raw_insert = _patch_quote_creation(monkeypatch)
        from ai_rfq_engine.handlers import availability

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

    @pytest.mark.unit
    def test_quote_creation_rejects_unavailable_capacity_before_save(
        self, info, monkeypatch
    ):
        raw_insert = _patch_quote_creation(monkeypatch)
        from ai_rfq_engine.handlers import availability as availability_mod
        from ai_rfq_engine.models import quote_item as quote_item_module

        def _raise_unavailable(*args, **kwargs):
            raise ValueError("Requested provider item is not available for the service window")

        monkeypatch.setattr(
            availability_mod,
            "dispatch_acquire_hold",
            lambda *args, **kwargs: {"available": False},
        )
        monkeypatch.setattr(
            quote_item_module,
            "_enforce_availability",
            _raise_unavailable,
        )
        with pytest.raises(ValueError, match="not available"):
            raw_insert(info, **_quote_kwargs())
        assert FakeSavedQuoteItem.captured is None


class TestCheckAvailabilityGraphQL:
    @pytest.mark.unit
    def test_check_availability_query_returns_available(self, info, monkeypatch):
        from ai_rfq_engine.queries.availability import resolve_check_availability

        _patch_batches(
            monkeypatch,
            [_make_batch(pendulum.datetime(2026, 5, 30, tz="UTC"),
                        pendulum.datetime(2026, 6, 5, tz="UTC"))],
        )
        result = resolve_check_availability(
            info,
            provider_item_uuid="room-1",
            service_start_at=pendulum.datetime(2026, 6, 1, tz="UTC"),
            service_end_at=pendulum.datetime(2026, 6, 2, tz="UTC"),
        )
        assert result.available is True

    @pytest.mark.unit
    def test_check_availability_query_returns_not_available(self, info, monkeypatch):
        from ai_rfq_engine.queries.availability import resolve_check_availability

        _patch_batches(monkeypatch, [])
        result = resolve_check_availability(
            info,
            provider_item_uuid="room-1",
            service_start_at=pendulum.datetime(2026, 6, 1, tz="UTC"),
            service_end_at=pendulum.datetime(2026, 6, 2, tz="UTC"),
        )
        assert result.available is False


class TestQuoteHoldLifecycle:
    @pytest.mark.unit
    def test_accepting_quote_confirms_held_quote_items(self, info, monkeypatch):
        from ai_rfq_engine.handlers import availability as availability_handler
        from ai_rfq_engine.models import provider_item as provider_item_model
        from ai_rfq_engine.models import quote as quote_model
        from ai_rfq_engine.models import quote_item as quote_item_model

        confirmed = []
        quote_item = SimpleNamespace(
            partition_key="tenant-test",
            provider_item_uuid="room-1",
            batch_no="BATCH-001",
            hold_token="hold-1",
        )
        monkeypatch.setattr(
            quote_item_model, "get_quote_items_by_quote", lambda *args: [quote_item]
        )
        monkeypatch.setattr(
            provider_item_model,
            "get_provider_item",
            lambda *args: SimpleNamespace(availability_mode="require_hold"),
        )
        monkeypatch.setattr(
            availability_handler,
            "dispatch_confirm_hold",
            lambda *args, **kwargs: confirmed.append(kwargs),
        )

        quote_model._confirm_quote_item_holds(
            info, SimpleNamespace(quote_uuid="quote")
        )

        assert confirmed == [
            {
                "provider_item_uuid": "room-1",
                "batch_no": "BATCH-001",
                "hold_token": "hold-1",
            }
        ]

    @pytest.mark.unit
    def test_deleting_held_quote_item_releases_hold(self, info, monkeypatch):
        from ai_rfq_engine.handlers import availability as availability_handler
        from ai_rfq_engine.models import provider_item as provider_item_model
        from ai_rfq_engine.models import quote_item as quote_item_model

        released = []
        quote_item = SimpleNamespace(
            partition_key="tenant-test",
            provider_item_uuid="room-1",
            batch_no="BATCH-001",
            hold_token="hold-1",
        )
        monkeypatch.setattr(
            provider_item_model,
            "get_provider_item",
            lambda *args: SimpleNamespace(availability_mode="require_hold"),
        )
        monkeypatch.setattr(
            availability_handler,
            "dispatch_release_hold",
            lambda *args, **kwargs: released.append(kwargs),
        )

        quote_item_model._release_availability_hold(info, quote_item)

        assert released == [
            {
                "provider_item_uuid": "room-1",
                "batch_no": "BATCH-001",
                "hold_token": "hold-1",
            }
        ]
