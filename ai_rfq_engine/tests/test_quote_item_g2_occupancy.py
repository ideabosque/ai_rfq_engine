#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Unit tests for G2 occupancy pricing mode on ``insert_update_quote_item``.

Occupancy mode is the third pricing path alongside ``unit`` and ``per_pax_type``:

    subtotal = qty * (base_rate + Σ extra-pax-surcharges)

where each pax_type can be partly absorbed by ``base_occupancy`` and any guests
over that count incur ``extra_pax_surcharges[pax_type]`` per unit.

Tests run without DynamoDB by monkey-patching the model getters that
``insert_update_quote_item`` reaches across.
"""
from __future__ import annotations

__author__ = "bibow"

from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest


# --- Fakes ------------------------------------------------------------------ #


class FakeItem:
    """Item with ``pricing_mode="occupancy"``."""

    pricing_mode = "occupancy"


class FakeTier:
    """Stand-in for an ItemPriceTierType returned by the resolver."""

    def __init__(
        self,
        *,
        price_per_uom: Optional[float] = 200.0,
        base_occupancy: Optional[Dict[str, float]] = None,
        extra_pax_surcharges: Optional[Dict[str, float]] = None,
    ) -> None:
        self.price_per_uom = price_per_uom
        self.base_occupancy = base_occupancy
        self.extra_pax_surcharges = extra_pax_surcharges


class FakeQuote:
    """Minimal Quote stand-in; no FX applied."""

    currency: Optional[str] = None
    display_currency: Optional[str] = None
    fx_rate: Optional[float] = None


class FakeBatch:
    cancellation_policy_uuid: Optional[str] = None


class FakeSavedRow:
    """Captures kwargs that would have been persisted."""

    captured: Dict[str, Any] = {}

    def __init__(self, quote_uuid: str, quote_item_uuid: str, **cols: Any) -> None:
        FakeSavedRow.captured = {
            "quote_uuid": quote_uuid,
            "quote_item_uuid": quote_item_uuid,
            **cols,
        }

    def save(self) -> None:
        return None


# --- Fixtures --------------------------------------------------------------- #


@pytest.fixture
def info():
    return SimpleNamespace(context={"partition_key": "tenant-test"})


@pytest.fixture
def patched_quote_item(monkeypatch):
    """
    Patch the boundaries ``insert_update_quote_item`` reaches across so the
    occupancy branch can be exercised without a database.
    """
    from ai_rfq_engine.models import cancellation_policy as cp_model
    from ai_rfq_engine.models import item as item_model
    from ai_rfq_engine.models import provider_item as provider_item_model
    from ai_rfq_engine.models import provider_item_batches as pib_model
    from ai_rfq_engine.models import quote as quote_model
    from ai_rfq_engine.models import quote_item as quote_item_model

    FakeSavedRow.captured = {}

    monkeypatch.setattr(item_model, "get_item", lambda *args: FakeItem())
    monkeypatch.setattr(quote_item_model, "QuoteItemModel", FakeSavedRow)
    monkeypatch.setattr(quote_model, "update_quote_totals", lambda *args: None)
    monkeypatch.setattr(quote_model, "get_quote", lambda *args: FakeQuote())
    monkeypatch.setattr(
        provider_item_model,
        "get_provider_item",
        lambda *args: SimpleNamespace(availability_mode="none"),
    )
    monkeypatch.setattr(
        pib_model, "get_provider_item_batch", lambda *args: FakeBatch()
    )
    monkeypatch.setattr(cp_model, "get_cancellation_policy_count", lambda *args: 0)
    return quote_item_model


def _raw_insert(quote_item_module):
    """Strip the model's nested decorators so we can call the inner function
    directly with ``entity=None`` and our fake collaborators."""
    return quote_item_module.insert_update_quote_item.__wrapped__.__wrapped__


# --- Pricing math tests ----------------------------------------------------- #


class TestG2OccupancyPricing:
    def test_within_base_occupancy_uses_base_rate_only(
        self, info, patched_quote_item, monkeypatch
    ):
        """2 adults in a room with base 2 -> no surcharge applies."""
        monkeypatch.setattr(
            patched_quote_item,
            "_get_occupancy_pricing_tier",
            lambda *a, **kw: FakeTier(
                price_per_uom=200.0,
                base_occupancy={"adult": 2},
                extra_pax_surcharges={"adult": 50, "child": 25},
            ),
        )
        raw = _raw_insert(patched_quote_item)
        raw(
            info,
            entity=None,
            quote_uuid="q",
            quote_item_uuid="qi",
            request_uuid="r",
            item_uuid="i",
            provider_item_uuid="p",
            segment_uuid="s",
            qty=3.0,  # 3 room-nights
            pax_breakdown={"adult": 2},
            updated_by="t",
        )
        c = FakeSavedRow.captured
        assert c["price_per_uom"] == pytest.approx(200.0)
        assert c["subtotal"] == pytest.approx(600.0)  # 3 nights * 200

    def test_extra_adult_charges_surcharge_per_unit(
        self, info, patched_quote_item, monkeypatch
    ):
        """3 adults in a base-2 room -> 1 extra adult @ $50/night."""
        monkeypatch.setattr(
            patched_quote_item,
            "_get_occupancy_pricing_tier",
            lambda *a, **kw: FakeTier(
                price_per_uom=200.0,
                base_occupancy={"adult": 2},
                extra_pax_surcharges={"adult": 50, "child": 25},
            ),
        )
        raw = _raw_insert(patched_quote_item)
        raw(
            info,
            entity=None,
            quote_uuid="q",
            quote_item_uuid="qi",
            request_uuid="r",
            item_uuid="i",
            provider_item_uuid="p",
            segment_uuid="s",
            qty=2.0,  # 2 nights
            pax_breakdown={"adult": 3},
            updated_by="t",
        )
        c = FakeSavedRow.captured
        # per-night = 200 + 1*50 = 250; 2 nights -> 500
        assert c["price_per_uom"] == pytest.approx(250.0)
        assert c["subtotal"] == pytest.approx(500.0)

    def test_mixed_pax_types_with_separate_base_inclusion(
        self, info, patched_quote_item, monkeypatch
    ):
        """
        2 adults + 2 children with base {adult: 2, child: 0} -> children both
        extras (since child base is 0); adults within base.
        per-night = 200 + 2*25 = 250; 1 night = 250.
        """
        monkeypatch.setattr(
            patched_quote_item,
            "_get_occupancy_pricing_tier",
            lambda *a, **kw: FakeTier(
                price_per_uom=200.0,
                base_occupancy={"adult": 2, "child": 0},
                extra_pax_surcharges={"adult": 50, "child": 25},
            ),
        )
        raw = _raw_insert(patched_quote_item)
        raw(
            info,
            entity=None,
            quote_uuid="q",
            quote_item_uuid="qi",
            request_uuid="r",
            item_uuid="i",
            provider_item_uuid="p",
            segment_uuid="s",
            qty=1.0,
            pax_breakdown={"adult": 2, "child": 2},
            updated_by="t",
        )
        c = FakeSavedRow.captured
        assert c["price_per_uom"] == pytest.approx(250.0)
        assert c["subtotal"] == pytest.approx(250.0)

    def test_missing_pax_type_in_base_treated_as_zero_included(
        self, info, patched_quote_item, monkeypatch
    ):
        """If a pax_type is absent from base_occupancy, all of them are extras."""
        monkeypatch.setattr(
            patched_quote_item,
            "_get_occupancy_pricing_tier",
            lambda *a, **kw: FakeTier(
                price_per_uom=200.0,
                base_occupancy={"adult": 2},  # child not listed
                extra_pax_surcharges={"adult": 50, "child": 25},
            ),
        )
        raw = _raw_insert(patched_quote_item)
        raw(
            info,
            entity=None,
            quote_uuid="q",
            quote_item_uuid="qi",
            request_uuid="r",
            item_uuid="i",
            provider_item_uuid="p",
            segment_uuid="s",
            qty=1.0,
            pax_breakdown={"adult": 2, "child": 1},
            updated_by="t",
        )
        c = FakeSavedRow.captured
        # adults within base; 1 child extra @ 25
        assert c["price_per_uom"] == pytest.approx(225.0)
        assert c["subtotal"] == pytest.approx(225.0)


# --- Validation tests ------------------------------------------------------- #


class TestG2OccupancyValidation:
    def test_missing_pax_breakdown_raises(self, info, patched_quote_item, monkeypatch):
        monkeypatch.setattr(
            patched_quote_item,
            "_get_occupancy_pricing_tier",
            lambda *a, **kw: FakeTier(),
        )
        raw = _raw_insert(patched_quote_item)
        with pytest.raises(ValueError, match="pax_breakdown is required for occupancy"):
            raw(
                info,
                entity=None,
                quote_uuid="q",
                quote_item_uuid="qi",
                request_uuid="r",
                item_uuid="i",
                provider_item_uuid="p",
                segment_uuid="s",
                qty=1.0,
                updated_by="t",
            )

    def test_empty_pax_breakdown_raises(self, info, patched_quote_item, monkeypatch):
        monkeypatch.setattr(
            patched_quote_item,
            "_get_occupancy_pricing_tier",
            lambda *a, **kw: FakeTier(),
        )
        raw = _raw_insert(patched_quote_item)
        with pytest.raises(ValueError, match="pax_breakdown is required for occupancy"):
            raw(
                info,
                entity=None,
                quote_uuid="q",
                quote_item_uuid="qi",
                request_uuid="r",
                item_uuid="i",
                provider_item_uuid="p",
                segment_uuid="s",
                qty=1.0,
                pax_breakdown={},
                updated_by="t",
            )

    def test_no_matching_tier_raises(self, info, patched_quote_item, monkeypatch):
        monkeypatch.setattr(
            patched_quote_item,
            "_get_occupancy_pricing_tier",
            lambda *a, **kw: None,
        )
        raw = _raw_insert(patched_quote_item)
        with pytest.raises(ValueError, match="No occupancy base tier"):
            raw(
                info,
                entity=None,
                quote_uuid="q",
                quote_item_uuid="qi",
                request_uuid="r",
                item_uuid="i",
                provider_item_uuid="p",
                segment_uuid="s",
                qty=1.0,
                pax_breakdown={"adult": 2},
                updated_by="t",
            )

    def test_tier_without_price_per_uom_raises(
        self, info, patched_quote_item, monkeypatch
    ):
        monkeypatch.setattr(
            patched_quote_item,
            "_get_occupancy_pricing_tier",
            lambda *a, **kw: FakeTier(price_per_uom=None),
        )
        raw = _raw_insert(patched_quote_item)
        with pytest.raises(ValueError, match="No occupancy base tier"):
            raw(
                info,
                entity=None,
                quote_uuid="q",
                quote_item_uuid="qi",
                request_uuid="r",
                item_uuid="i",
                provider_item_uuid="p",
                segment_uuid="s",
                qty=1.0,
                pax_breakdown={"adult": 2},
                updated_by="t",
            )

    def test_over_base_pax_type_without_surcharge_raises(
        self, info, patched_quote_item, monkeypatch
    ):
        """
        If a pax_type appears in pax_breakdown above the included count but the
        tier has no surcharge for that type, surface that as a configuration
        error rather than silently treating the surcharge as zero.
        """
        monkeypatch.setattr(
            patched_quote_item,
            "_get_occupancy_pricing_tier",
            lambda *a, **kw: FakeTier(
                price_per_uom=200.0,
                base_occupancy={"adult": 2},
                extra_pax_surcharges={"adult": 50},  # no child surcharge
            ),
        )
        raw = _raw_insert(patched_quote_item)
        with pytest.raises(
            ValueError, match="extra_pax_surcharges entry for over-base pax_type='child'"
        ):
            raw(
                info,
                entity=None,
                quote_uuid="q",
                quote_item_uuid="qi",
                request_uuid="r",
                item_uuid="i",
                provider_item_uuid="p",
                segment_uuid="s",
                qty=1.0,
                pax_breakdown={"adult": 2, "child": 1},
                updated_by="t",
            )

    def test_negative_count_in_pax_breakdown_raises(
        self, info, patched_quote_item, monkeypatch
    ):
        monkeypatch.setattr(
            patched_quote_item,
            "_get_occupancy_pricing_tier",
            lambda *a, **kw: FakeTier(),
        )
        raw = _raw_insert(patched_quote_item)
        with pytest.raises(ValueError, match="non-negative"):
            raw(
                info,
                entity=None,
                quote_uuid="q",
                quote_item_uuid="qi",
                request_uuid="r",
                item_uuid="i",
                provider_item_uuid="p",
                segment_uuid="s",
                qty=1.0,
                pax_breakdown={"adult": -1},
                updated_by="t",
            )


# --- Coerce helper unit tests ---------------------------------------------- #


class TestCoerceOccupancyMap:
    def test_none_returns_empty(self):
        from ai_rfq_engine.models.quote_item import _coerce_occupancy_map

        assert _coerce_occupancy_map(None) == {}

    def test_dict_passthrough_with_float_coercion(self):
        from ai_rfq_engine.models.quote_item import _coerce_occupancy_map

        assert _coerce_occupancy_map({"adult": 2, "child": "1"}) == {
            "adult": 2.0,
            "child": 1.0,
        }

    def test_map_attribute_as_dict_is_unwrapped(self):
        from ai_rfq_engine.models.quote_item import _coerce_occupancy_map

        class FakeMapAttr:
            def as_dict(self):
                return {"adult": 3.0}

        assert _coerce_occupancy_map(FakeMapAttr()) == {"adult": 3.0}

    def test_non_numeric_entries_are_skipped(self):
        from ai_rfq_engine.models.quote_item import _coerce_occupancy_map

        assert _coerce_occupancy_map({"adult": "abc", "child": 1}) == {"child": 1.0}
