#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Unit tests for G5 (FX application) and G6 (cancellation snapshot) on
``insert_update_quote_item``. Tests run without DynamoDB by monkey-patching
the model getters that the function calls.

Covers:
  G5
    - Same-currency quote: subtotal == subtotal_native, FX not applied.
    - Cross-currency quote with locked rate: subtotal == native * fx_rate.
    - Unconfigured quote (no fx_rate set): subtotal == native (procurement default).
    - User-provided ``currency`` kwarg overrides the Quote default.
  G6
    - Snapshot created when batch has cancellation_policy_uuid.
    - No snapshot when batch_no is missing (no batch pinned).
    - No snapshot when batch has no cancellation_policy_uuid.
    - User-provided request_data is preserved alongside the snapshot.
"""
from __future__ import annotations

__author__ = "bibow"

from types import SimpleNamespace
from typing import Any, Dict

import pendulum
import pytest


# --- Fakes & fixtures ------------------------------------------------------- #


class FakeItem:
    """Stand-in for ItemModel; only the attributes the function reads matter."""

    def __init__(self, pricing_mode: str = "unit") -> None:
        self.pricing_mode = pricing_mode


class FakeQuote:
    """Stand-in for QuoteModel; carries the G5 FX fields."""

    def __init__(
        self,
        *,
        currency: str | None = None,
        display_currency: str | None = None,
        fx_rate: float | None = None,
    ) -> None:
        self.currency = currency
        self.display_currency = display_currency
        self.fx_rate = fx_rate


class FakeBatch:
    def __init__(self, *, cancellation_policy_uuid: str | None = None) -> None:
        self.cancellation_policy_uuid = cancellation_policy_uuid


class FakePolicy:
    def __init__(
        self,
        *,
        policy_uuid: str,
        label: str = "Standard",
        description: str = "Standard refund tiers",
        tiers: dict | None = None,
        notes_template_uuid: str | None = None,
    ) -> None:
        self.policy_uuid = policy_uuid
        self.label = label
        self.description = description
        self.tiers = tiers or {
            "tiers": [
                {"days_before_service_gte": 14, "refund_pct": 1.0},
                {"days_before_service_gte": 0, "refund_pct": 0.0},
            ]
        }
        self.notes_template_uuid = notes_template_uuid


class FakeSavedRow:
    """Captures the kwargs handed to ``QuoteItemModel.__init__`` so tests can
    assert what would have been persisted without touching DynamoDB."""

    captured: Dict[str, Any] = {}

    def __init__(self, quote_uuid: str, quote_item_uuid: str, **cols: Any) -> None:
        FakeSavedRow.captured = {
            "quote_uuid": quote_uuid,
            "quote_item_uuid": quote_item_uuid,
            **cols,
        }

    def save(self) -> None:
        return None


@pytest.fixture
def info():
    return SimpleNamespace(context={"partition_key": "tenant-test"})


@pytest.fixture
def patched_quote_item(monkeypatch):
    """
    Patch every external boundary ``insert_update_quote_item`` reaches across
    so tests run in isolation. Each test then layers in the specific behavior
    (e.g. a different Quote currency, an empty batch) it cares about.
    """
    from ai_rfq_engine.models import item as item_model
    from ai_rfq_engine.models import quote as quote_model
    from ai_rfq_engine.models import quote_item as quote_item_model
    from ai_rfq_engine.models import provider_item as provider_item_model

    FakeSavedRow.captured = {}

    monkeypatch.setattr(item_model, "get_item", lambda *args: FakeItem())
    monkeypatch.setattr(quote_item_model, "QuoteItemModel", FakeSavedRow)
    monkeypatch.setattr(quote_model, "update_quote_totals", lambda *args: None)
    # Default: tier returns a price of 100 in native currency.
    monkeypatch.setattr(
        quote_item_model,
        "get_price_per_uom",
        lambda *args, pax_type=None, **kwargs: 100.0,
    )
    # Default: no parent quote model (G5 inactive).
    monkeypatch.setattr(quote_model, "get_quote", lambda *args: FakeQuote())
    monkeypatch.setattr(
        provider_item_model,
        "get_provider_item",
        lambda *args: SimpleNamespace(availability_mode="none"),
    )
    # Default: no batch / no policy (G6 inactive).
    from ai_rfq_engine.models import provider_item_batches as pib_model
    from ai_rfq_engine.models import cancellation_policy as cp_model

    monkeypatch.setattr(
        pib_model, "get_provider_item_batch", lambda *args: FakeBatch()
    )
    monkeypatch.setattr(cp_model, "get_cancellation_policy_count", lambda *args: 0)
    monkeypatch.setattr(
        cp_model,
        "get_cancellation_policy",
        lambda *args: FakePolicy(policy_uuid="should-not-fire"),
    )
    return quote_item_model


def _raw_insert(quote_item_module):
    """Strip the model's nested decorators so we can call the inner function
    directly with ``entity=None`` and our fake collaborators."""
    return quote_item_module.insert_update_quote_item.__wrapped__.__wrapped__


# --- G5 FX tests ----------------------------------------------------------- #


class TestG5FxApplication:
    def test_same_currency_no_fx_applied(self, info, patched_quote_item, monkeypatch):
        from ai_rfq_engine.models import quote as quote_model

        # Quote is USD display / USD native with a locked rate of 1.0
        monkeypatch.setattr(
            quote_model,
            "get_quote",
            lambda *args: FakeQuote(
                currency="USD", display_currency="USD", fx_rate=1.0
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
            qty=2.0,
            updated_by="t",
        )
        c = FakeSavedRow.captured
        # FX rule: display_currency == native_currency -> no multiplication.
        assert c["subtotal_native"] == pytest.approx(200.0)
        assert c["subtotal"] == pytest.approx(200.0)
        assert c["currency"] == "USD"

    def test_cross_currency_applies_locked_rate(
        self, info, patched_quote_item, monkeypatch
    ):
        from ai_rfq_engine.models import quote as quote_model

        # Supplier prices in JPY, customer sees USD at rate 0.0067
        monkeypatch.setattr(
            quote_model,
            "get_quote",
            lambda *args: FakeQuote(
                currency="JPY", display_currency="USD", fx_rate=0.0067
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
            qty=2.0,
            updated_by="t",
        )
        c = FakeSavedRow.captured
        assert c["currency"] == "JPY"  # defaulted from quote
        assert c["subtotal_native"] == pytest.approx(200.0)
        assert c["subtotal"] == pytest.approx(200.0 * 0.0067)

    def test_unconfigured_quote_no_fx(self, info, patched_quote_item):
        """Existing procurement quotes (no FX fields) keep their current behavior."""
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
            qty=2.0,
            updated_by="t",
        )
        c = FakeSavedRow.captured
        # Default FakeQuote has currency=None, display_currency=None, fx_rate=None.
        # No FX should be applied; subtotal == native amount.
        assert c["subtotal"] == pytest.approx(200.0)
        assert c["subtotal_native"] == pytest.approx(200.0)
        # Currency not set anywhere — the quote item carries None.
        assert c.get("currency") is None

    def test_caller_provided_currency_overrides_quote_default(
        self, info, patched_quote_item, monkeypatch
    ):
        from ai_rfq_engine.models import quote as quote_model

        monkeypatch.setattr(
            quote_model,
            "get_quote",
            lambda *args: FakeQuote(
                currency="JPY", display_currency="USD", fx_rate=0.0067
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
            qty=2.0,
            updated_by="t",
            currency="EUR",  # caller forces EUR as the line's native currency
        )
        c = FakeSavedRow.captured
        assert c["currency"] == "EUR"
        # display_currency (USD) != native (EUR) so FX still applies with the
        # quote's locked rate. This is the conservative interpretation; if the
        # business wants user-provided currency to bypass FX, that's a separate
        # design decision.
        assert c["subtotal"] == pytest.approx(200.0 * 0.0067)


# --- G6 cancellation snapshot tests ---------------------------------------- #


class TestG6CancellationSnapshot:
    def test_snapshot_captured_when_batch_has_policy(
        self, info, patched_quote_item, monkeypatch
    ):
        from ai_rfq_engine.models import cancellation_policy as cp_model
        from ai_rfq_engine.models import provider_item_batches as pib_model

        monkeypatch.setattr(
            pib_model,
            "get_provider_item_batch",
            lambda *args: FakeBatch(cancellation_policy_uuid="pol-001"),
        )
        monkeypatch.setattr(cp_model, "get_cancellation_policy_count", lambda *args: 1)
        monkeypatch.setattr(
            cp_model,
            "get_cancellation_policy",
            lambda *args: FakePolicy(
                policy_uuid="pol-001",
                label="Standard 14/0",
                description="Free <14d, no refund <48h",
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
            batch_no="batch-001",
            segment_uuid="s",
            qty=1.0,
            updated_by="t",
        )
        c = FakeSavedRow.captured
        rd = c.get("request_data") or {}
        snapshot = rd.get("cancellation_policy_snapshot")
        assert snapshot is not None
        assert snapshot["policy_uuid"] == "pol-001"
        assert snapshot["label"] == "Standard 14/0"
        # tiers preserved verbatim from the policy row
        assert snapshot["tiers"]["tiers"][0]["refund_pct"] == 1.0
        # immutable timestamp recorded
        assert snapshot["snapshotted_at"]

    def test_no_snapshot_when_batch_not_pinned(self, info, patched_quote_item):
        """No batch_no means no policy lookup; request_data stays untouched."""
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
            updated_by="t",
        )
        c = FakeSavedRow.captured
        assert c.get("request_data") in (None, {})

    def test_no_snapshot_when_batch_has_no_policy(
        self, info, patched_quote_item, monkeypatch
    ):
        from ai_rfq_engine.models import provider_item_batches as pib_model

        # Default fake batch already has cancellation_policy_uuid=None.
        # Add the batch_no kwarg to confirm we look it up but find no policy.
        monkeypatch.setattr(
            pib_model, "get_provider_item_batch", lambda *args: FakeBatch()
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
            batch_no="batch-001",
            segment_uuid="s",
            qty=1.0,
            updated_by="t",
        )
        c = FakeSavedRow.captured
        assert c.get("request_data") in (None, {})

    def test_user_provided_request_data_is_preserved(
        self, info, patched_quote_item, monkeypatch
    ):
        from ai_rfq_engine.models import cancellation_policy as cp_model
        from ai_rfq_engine.models import provider_item_batches as pib_model

        monkeypatch.setattr(
            pib_model,
            "get_provider_item_batch",
            lambda *args: FakeBatch(cancellation_policy_uuid="pol-002"),
        )
        monkeypatch.setattr(cp_model, "get_cancellation_policy_count", lambda *args: 1)
        monkeypatch.setattr(
            cp_model,
            "get_cancellation_policy",
            lambda *args: FakePolicy(policy_uuid="pol-002"),
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
            batch_no="batch-002",
            segment_uuid="s",
            qty=1.0,
            updated_by="t",
            request_data={"special_instructions": "no peanuts"},
        )
        c = FakeSavedRow.captured
        rd = c["request_data"]
        # Caller's payload preserved...
        assert rd["special_instructions"] == "no peanuts"
        # ...and the snapshot is added alongside it.
        assert rd["cancellation_policy_snapshot"]["policy_uuid"] == "pol-002"

    def test_user_provided_snapshot_is_not_clobbered(
        self, info, patched_quote_item, monkeypatch
    ):
        """A caller pre-populating the snapshot key (rare but legal) wins;
        the auto-snapshot uses ``setdefault`` and never overwrites."""
        from ai_rfq_engine.models import cancellation_policy as cp_model
        from ai_rfq_engine.models import provider_item_batches as pib_model

        monkeypatch.setattr(
            pib_model,
            "get_provider_item_batch",
            lambda *args: FakeBatch(cancellation_policy_uuid="pol-003"),
        )
        monkeypatch.setattr(cp_model, "get_cancellation_policy_count", lambda *args: 1)
        monkeypatch.setattr(
            cp_model,
            "get_cancellation_policy",
            lambda *args: FakePolicy(policy_uuid="pol-003"),
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
            batch_no="batch-003",
            segment_uuid="s",
            qty=1.0,
            updated_by="t",
            request_data={
                "cancellation_policy_snapshot": {"policy_uuid": "caller-override"}
            },
        )
        c = FakeSavedRow.captured
        assert c["request_data"]["cancellation_policy_snapshot"]["policy_uuid"] == (
            "caller-override"
        )
