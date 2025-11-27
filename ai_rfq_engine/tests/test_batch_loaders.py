#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Unit tests for batch loaders (DataLoader implementations)."""
from __future__ import annotations

__author__ = "bibow"

import sys
import os
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path to allow imports when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from silvaengine_utility import Utility

from ai_rfq_engine.models.batch_loaders import (
    RequestLoaders,
    clear_loaders,
    get_loaders,
)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _mock_model(endpoint_id: str, range_attr: str, range_value: str, **extra):
    """Build a lightweight mock Pynamo model with attribute_values."""

    # Use a simple class instead of MagicMock to avoid __dict__ issues
    class MockModel:
        pass

    model = MockModel()
    model.endpoint_id = endpoint_id
    setattr(model, range_attr, range_value)
    model.__dict__["attribute_values"] = {
        "endpoint_id": endpoint_id,
        range_attr: range_value,
        **extra,
    }
    return model


# ============================================================================
# BATCH LOADER UNIT TESTS
# ============================================================================


@pytest.mark.unit
def test_batch_loaders_cached_per_context():
    """Test that loaders are cached per context and can be cleared."""
    context = {}
    first = get_loaders(context)
    second = get_loaders(context)
    assert first is second
    clear_loaders(context)
    third = get_loaders(context)
    assert third is not first


@pytest.mark.unit
def test_item_loader_batches_requests():
    """Test that ItemLoader successfully loads multiple items and deduplicates requests."""
    from ai_rfq_engine.models.batch_loaders import ItemLoader

    context = {"logger": MagicMock()}
    # Disable cache for testing
    loader = ItemLoader(logger=context["logger"], cache_enabled=False)

    i1 = _mock_model("endpoint-1", "item_uuid", "item-1", item_name="Item 1")
    i2 = _mock_model("endpoint-1", "item_uuid", "item-2", item_name="Item 2")

    # Verify mock models are correct
    assert i1.endpoint_id == "endpoint-1", "Mock i1 endpoint_id not set"
    assert i1.item_uuid == "item-1", "Mock i1 item_uuid not set"
    normalized_i1 = Utility.json_normalize(i1.__dict__["attribute_values"])
    assert (
        normalized_i1["item_uuid"] == "item-1"
    ), f"Normalized i1 incorrect: {normalized_i1}"

    with patch("ai_rfq_engine.models.item.ItemModel.batch_get") as mock_batch:
        # Mock should return an iterable of models
        mock_batch.return_value = [i1, i2]

        # Test the batch_load_fn directly
        keys = [("endpoint-1", "item-1"), ("endpoint-1", "item-2")]
        result_promise = loader.batch_load_fn(keys)
        results = result_promise.get()

    # Verify batch_get was called once
    assert mock_batch.call_count == 1, f"Expected 1 call, got {mock_batch.call_count}"

    # Debug output
    if results[0] is None:
        print(f"Results: {results}")
        print(f"Mock was called with: {mock_batch.call_args_list}")

    # Verify results match keys
    assert (
        results[0] is not None
    ), f"First result should not be None. Results: {results}"
    assert (
        results[0]["item_uuid"] == "item-1"
    ), f"Expected item-1, got {results[0].get('item_uuid')}"
    assert (
        results[1]["item_uuid"] == "item-2"
    ), f"Expected item-2, got {results[1].get('item_uuid')}"


@pytest.mark.unit
def test_provider_item_loader_batches_requests():
    """Test that ProviderItemLoader successfully loads multiple provider items."""
    from ai_rfq_engine.models.batch_loaders import ProviderItemLoader

    context = {"logger": MagicMock()}
    loader = ProviderItemLoader(logger=context["logger"], cache_enabled=False)

    p1 = _mock_model(
        "endpoint-1", "provider_item_uuid", "pi-1", base_price_per_uom="10.00"
    )
    p2 = _mock_model(
        "endpoint-1", "provider_item_uuid", "pi-2", base_price_per_uom="20.00"
    )

    with patch(
        "ai_rfq_engine.models.provider_item.ProviderItemModel.batch_get"
    ) as mock_batch:
        mock_batch.return_value = [p1, p2]

        # Test the batch_load_fn directly
        keys = [("endpoint-1", "pi-1"), ("endpoint-1", "pi-2")]
        result_promise = loader.batch_load_fn(keys)
        results = result_promise.get()

    # Verify batch_get was called once
    assert mock_batch.call_count == 1, f"Expected 1 call, got {mock_batch.call_count}"

    # Verify results match keys
    assert results[0] is not None, "First result should not be None"
    assert results[0]["provider_item_uuid"] == "pi-1"
    assert results[1]["base_price_per_uom"] == "20.00"


@pytest.mark.unit
def test_segment_loader_batches_requests():
    """Test that SegmentLoader successfully loads multiple segments."""
    from ai_rfq_engine.models.batch_loaders import SegmentLoader

    context = {"logger": MagicMock()}
    loader = SegmentLoader(logger=context["logger"], cache_enabled=False)

    s1 = _mock_model("endpoint-1", "segment_uuid", "seg-1", segment_name="Segment 1")
    s2 = _mock_model("endpoint-1", "segment_uuid", "seg-2", segment_name="Segment 2")

    with patch("ai_rfq_engine.models.segment.SegmentModel.batch_get") as mock_batch:
        mock_batch.return_value = [s1, s2]

        # Test the batch_load_fn directly
        keys = [("endpoint-1", "seg-1"), ("endpoint-1", "seg-2")]
        result_promise = loader.batch_load_fn(keys)
        results = result_promise.get()

    # Verify batch_get was called once
    assert mock_batch.call_count == 1, f"Expected 1 call, got {mock_batch.call_count}"

    # Verify results match keys
    assert results[0] is not None, "First result should not be None"
    assert results[0]["segment_uuid"] == "seg-1"
    assert results[1]["segment_name"] == "Segment 2"


@pytest.mark.unit
def test_request_loader_batches_requests():
    """Test that RequestLoader successfully loads multiple requests."""
    from ai_rfq_engine.models.batch_loaders import RequestLoader

    context = {"logger": MagicMock()}
    loader = RequestLoader(logger=context["logger"], cache_enabled=False)

    r1 = _mock_model("endpoint-1", "request_uuid", "req-1", request_title="RFQ 1")
    r2 = _mock_model("endpoint-1", "request_uuid", "req-2", request_title="RFQ 2")

    with patch("ai_rfq_engine.models.request.RequestModel.batch_get") as mock_batch:
        mock_batch.return_value = [r1, r2]

        # Test the batch_load_fn directly
        keys = [("endpoint-1", "req-1"), ("endpoint-1", "req-2")]
        result_promise = loader.batch_load_fn(keys)
        results = result_promise.get()

    # Verify batch_get was called once
    assert mock_batch.call_count == 1, f"Expected 1 call, got {mock_batch.call_count}"

    # Verify results match keys
    assert results[0] is not None, "First result should not be None"
    assert results[0]["request_uuid"] == "req-1"
    assert results[1]["request_title"] == "RFQ 2"


@pytest.mark.unit
def test_quote_loader_batches_requests():
    """Test that QuoteLoader successfully loads multiple quotes."""
    from ai_rfq_engine.models.batch_loaders import QuoteLoader

    context = {"logger": MagicMock()}
    loader = QuoteLoader(logger=context["logger"], cache_enabled=False)

    q1 = _mock_model(
        "req-1", "quote_uuid", "quote-1", total_quote_amount="1000.00"
    )
    q2 = _mock_model(
        "req-1", "quote_uuid", "quote-2", total_quote_amount="2000.00"
    )
    # Note: QuoteModel uses (request_uuid, quote_uuid) as composite key
    q1.request_uuid = "req-1"
    q2.request_uuid = "req-1"
    q1.__dict__["attribute_values"]["request_uuid"] = "req-1"
    q2.__dict__["attribute_values"]["request_uuid"] = "req-1"

    with patch("ai_rfq_engine.models.quote.QuoteModel.batch_get") as mock_batch:
        mock_batch.return_value = [q1, q2]

        # Test the batch_load_fn directly
        keys = [("req-1", "quote-1"), ("req-1", "quote-2")]
        result_promise = loader.batch_load_fn(keys)
        results = result_promise.get()

    # Verify batch_get was called once
    assert mock_batch.call_count == 1, f"Expected 1 call, got {mock_batch.call_count}"

    # Verify results match keys
    assert results[0] is not None, "First result should not be None"
    assert results[0]["quote_uuid"] == "quote-1"
    assert results[1]["total_quote_amount"] == "2000.00"


@pytest.mark.unit
def test_loader_deduplicates_keys():
    """Test that loaders deduplicate identical keys."""
    from ai_rfq_engine.models.batch_loaders import ItemLoader

    context = {"logger": MagicMock()}
    loader = ItemLoader(logger=context["logger"], cache_enabled=False)

    i1 = _mock_model("endpoint-1", "item_uuid", "item-1", item_name="Item 1")

    with patch("ai_rfq_engine.models.item.ItemModel.batch_get") as mock_batch:
        mock_batch.return_value = [i1]

        # Request same item twice (should deduplicate)
        keys = [("endpoint-1", "item-1"), ("endpoint-1", "item-1")]
        result_promise = loader.batch_load_fn(keys)
        results = result_promise.get()

    # Verify batch_get was called once with deduplicated keys
    assert mock_batch.call_count == 1
    # Both results should be the same item
    assert results[0]["item_uuid"] == "item-1"
    assert results[1]["item_uuid"] == "item-1"


@pytest.mark.unit
def test_loader_handles_missing_items():
    """Test that loaders handle missing items gracefully."""
    from ai_rfq_engine.models.batch_loaders import ItemLoader

    context = {"logger": MagicMock()}
    loader = ItemLoader(logger=context["logger"], cache_enabled=False)

    i1 = _mock_model("endpoint-1", "item_uuid", "item-1", item_name="Item 1")
    # item-2 is missing (not returned by batch_get)

    with patch("ai_rfq_engine.models.item.ItemModel.batch_get") as mock_batch:
        mock_batch.return_value = [i1]  # Only item-1 returned

        # Request item-1 and item-2
        keys = [("endpoint-1", "item-1"), ("endpoint-1", "item-2")]
        result_promise = loader.batch_load_fn(keys)
        results = result_promise.get()

    # Verify batch_get was called once
    assert mock_batch.call_count == 1
    # First result should exist
    assert results[0]["item_uuid"] == "item-1"
    # Second result should be None (not found)
    assert results[1] is None


@pytest.mark.unit
def test_request_loaders_container():
    """Test that RequestLoaders container initializes all loaders."""
    context = {"logger": MagicMock()}
    loaders = RequestLoaders(context)

    # Verify all loaders are initialized
    assert hasattr(loaders, "item_loader")
    assert hasattr(loaders, "provider_item_loader")
    assert hasattr(loaders, "provider_items_by_item_loader")
    assert hasattr(loaders, "provider_item_batch_list_loader")
    assert hasattr(loaders, "item_price_tier_by_provider_item_loader")
    assert hasattr(loaders, "item_price_tier_by_item_loader")
    assert hasattr(loaders, "quote_item_list_loader")
    assert hasattr(loaders, "installment_list_loader")
    assert hasattr(loaders, "discount_rule_by_item_loader")
    assert hasattr(loaders, "segment_loader")
    assert hasattr(loaders, "request_loader")
    assert hasattr(loaders, "quote_loader")

    # Verify each loader has correct type
    from ai_rfq_engine.models.batch_loaders import (
        ItemLoader,
        ProviderItemLoader,
        ProviderItemsByItemLoader,
        ProviderItemBatchListLoader,
        ItemPriceTierByProviderItemLoader,
        ItemPriceTierByItemLoader,
        QuoteItemListLoader,
        InstallmentListLoader,
        DiscountRuleByItemLoader,
        SegmentLoader,
        RequestLoader,
        QuoteLoader,
    )

    assert isinstance(loaders.item_loader, ItemLoader)
    assert isinstance(loaders.provider_item_loader, ProviderItemLoader)
    assert isinstance(loaders.provider_items_by_item_loader, ProviderItemsByItemLoader)
    assert isinstance(loaders.provider_item_batch_list_loader, ProviderItemBatchListLoader)
    assert isinstance(
        loaders.item_price_tier_by_provider_item_loader, ItemPriceTierByProviderItemLoader
    )
    assert isinstance(loaders.item_price_tier_by_item_loader, ItemPriceTierByItemLoader)
    assert isinstance(loaders.quote_item_list_loader, QuoteItemListLoader)
    assert isinstance(loaders.installment_list_loader, InstallmentListLoader)
    assert isinstance(loaders.discount_rule_by_item_loader, DiscountRuleByItemLoader)
    assert isinstance(loaders.segment_loader, SegmentLoader)
    assert isinstance(loaders.request_loader, RequestLoader)
    assert isinstance(loaders.quote_loader, QuoteLoader)


@pytest.mark.unit
def test_provider_item_batch_list_loader_fetches_batches():
    """Test ProviderItemBatchListLoader loads batches keyed by provider_item_uuid."""
    from ai_rfq_engine.models.batch_loaders import ProviderItemBatchListLoader

    context = {"logger": MagicMock()}
    loader = ProviderItemBatchListLoader(logger=context["logger"], cache_enabled=False)

    b1 = _mock_model(
        "endpoint-1",
        "batch_no",
        "batch-1",
        provider_item_uuid="pi-1",
        item_uuid="item-1",
    )
    b2 = _mock_model(
        "endpoint-1",
        "batch_no",
        "batch-2",
        provider_item_uuid="pi-1",
        item_uuid="item-2",
    )

    with patch(
        "ai_rfq_engine.models.provider_item_batches.ProviderItemBatchModel.query"
    ) as mock_query:
        mock_query.return_value = [b1, b2]

        result_promise = loader.batch_load_fn(["pi-1"])
        results = result_promise.get()

    mock_query.assert_called_once_with("pi-1")
    assert len(results[0]) == 2
    assert results[0][0]["batch_no"] == "batch-1"
    assert results[0][1]["item_uuid"] == "item-2"


@pytest.mark.unit
def test_item_price_tier_by_provider_item_loader_fetches_tiers():
    """Test ItemPriceTierByProviderItemLoader loads tiers keyed by (item_uuid, provider_item_uuid)."""
    from ai_rfq_engine.models.batch_loaders import ItemPriceTierByProviderItemLoader

    context = {"logger": MagicMock()}
    loader = ItemPriceTierByProviderItemLoader(
        logger=context["logger"], cache_enabled=False
    )

    t1 = _mock_model(
        "endpoint-1",
        "item_price_tier_uuid",
        "tier-1",
        item_uuid="item-1",
        provider_item_uuid="pi-1",
        margin_per_uom="0.1",
    )
    t2 = _mock_model(
        "endpoint-1",
        "item_price_tier_uuid",
        "tier-2",
        item_uuid="item-1",
        provider_item_uuid="pi-1",
        price_per_uom="12.50",
    )

    with patch(
        "ai_rfq_engine.models.item_price_tier.ItemPriceTierModel.provider_item_uuid_index.query"
    ) as mock_query:
        mock_query.return_value = [t1, t2]

        result_promise = loader.batch_load_fn([("item-1", "pi-1")])
        results = result_promise.get()

    mock_query.assert_called_once()
    assert len(results[0]) == 2
    assert results[0][0]["item_price_tier_uuid"] == "tier-1"
    assert results[0][1]["price_per_uom"] == "12.50"


@pytest.mark.unit
def test_item_price_tier_by_item_loader_fetches_tiers():
    """Test ItemPriceTierByItemLoader loads tiers keyed by item_uuid."""
    from ai_rfq_engine.models.batch_loaders import ItemPriceTierByItemLoader

    context = {"logger": MagicMock()}
    loader = ItemPriceTierByItemLoader(logger=context["logger"], cache_enabled=False)

    t1 = _mock_model(
        "endpoint-1",
        "item_price_tier_uuid",
        "tier-1",
        item_uuid="item-1",
        price_per_uom="10.00",
    )
    t2 = _mock_model(
        "endpoint-1",
        "item_price_tier_uuid",
        "tier-2",
        item_uuid="item-1",
        price_per_uom="15.00",
    )

    with patch("ai_rfq_engine.models.item_price_tier.ItemPriceTierModel.query") as mock_query:
        mock_query.return_value = [t1, t2]

        result_promise = loader.batch_load_fn(["item-1"])
        results = result_promise.get()

    mock_query.assert_called_once_with("item-1")
    assert len(results[0]) == 2
    assert results[0][0]["item_price_tier_uuid"] == "tier-1"
    assert results[0][1]["price_per_uom"] == "15.00"


@pytest.mark.unit
def test_quote_item_list_loader_fetches_items():
    """Test QuoteItemListLoader loads quote items keyed by quote_uuid."""
    from ai_rfq_engine.models.batch_loaders import QuoteItemListLoader

    context = {"logger": MagicMock()}
    loader = QuoteItemListLoader(logger=context["logger"], cache_enabled=False)

    qi1 = _mock_model(
        "endpoint-1",
        "quote_item_uuid",
        "qi-1",
        quote_uuid="quote-1",
        item_uuid="item-1",
    )
    qi2 = _mock_model(
        "endpoint-1",
        "quote_item_uuid",
        "qi-2",
        quote_uuid="quote-1",
        item_uuid="item-2",
    )

    with patch("ai_rfq_engine.models.quote_item.QuoteItemModel.query") as mock_query:
        mock_query.return_value = [qi1, qi2]

        result_promise = loader.batch_load_fn(["quote-1"])
        results = result_promise.get()

    mock_query.assert_called_once_with("quote-1")
    assert len(results[0]) == 2
    assert results[0][0]["quote_item_uuid"] == "qi-1"
    assert results[0][1]["item_uuid"] == "item-2"


@pytest.mark.unit
def test_provider_items_by_item_loader_fetches_items():
    """Test ProviderItemsByItemLoader loads provider items keyed by (endpoint_id, item_uuid)."""
    from ai_rfq_engine.models.batch_loaders import ProviderItemsByItemLoader

    context = {"logger": MagicMock()}
    loader = ProviderItemsByItemLoader(logger=context["logger"], cache_enabled=False)

    pi1 = _mock_model(
        "endpoint-1",
        "provider_item_uuid",
        "pi-1",
        item_uuid="item-1",
        base_price_per_uom="10.00",
    )
    pi2 = _mock_model(
        "endpoint-1",
        "provider_item_uuid",
        "pi-2",
        item_uuid="item-1",
        base_price_per_uom="12.00",
    )

    with patch(
        "ai_rfq_engine.models.provider_item.ProviderItemModel.item_uuid_index.query"
    ) as mock_query:
        mock_query.return_value = [pi1, pi2]

        result_promise = loader.batch_load_fn([("endpoint-1", "item-1")])
        results = result_promise.get()

    mock_query.assert_called_once()
    assert len(results[0]) == 2
    assert results[0][0]["provider_item_uuid"] == "pi-1"
    assert results[0][1]["base_price_per_uom"] == "12.00"


@pytest.mark.unit
def test_installment_list_loader_fetches_installments():
    """Test InstallmentListLoader loads installments keyed by quote_uuid."""
    from ai_rfq_engine.models.batch_loaders import InstallmentListLoader

    context = {"logger": MagicMock()}
    loader = InstallmentListLoader(logger=context["logger"], cache_enabled=False)

    inst1 = _mock_model(
        "endpoint-1",
        "installment_uuid",
        "inst-1",
        quote_uuid="quote-1",
        status="pending",
    )
    inst2 = _mock_model(
        "endpoint-1",
        "installment_uuid",
        "inst-2",
        quote_uuid="quote-1",
        status="paid",
    )

    with patch("ai_rfq_engine.models.installment.InstallmentModel.query") as mock_query:
        mock_query.return_value = [inst1, inst2]

        result_promise = loader.batch_load_fn(["quote-1"])
        results = result_promise.get()

    mock_query.assert_called_once_with("quote-1")
    assert len(results[0]) == 2
    assert results[0][0]["installment_uuid"] == "inst-1"
    assert results[0][1]["status"] == "paid"


@pytest.mark.unit
def test_discount_rule_by_item_loader_fetches_rules():
    """Test DiscountRuleByItemLoader loads discount rules keyed by item_uuid."""
    from ai_rfq_engine.models.batch_loaders import DiscountRuleByItemLoader

    context = {"logger": MagicMock()}
    loader = DiscountRuleByItemLoader(logger=context["logger"], cache_enabled=False)

    r1 = _mock_model("endpoint-1", "discount_rule_uuid", "dr-1", item_uuid="item-1", rule="A")
    r2 = _mock_model("endpoint-1", "discount_rule_uuid", "dr-2", item_uuid="item-1", rule="B")

    with patch("ai_rfq_engine.models.discount_rule.DiscountRuleModel.query") as mock_query:
        mock_query.return_value = [r1, r2]

        result_promise = loader.batch_load_fn(["item-1"])
        results = result_promise.get()

    mock_query.assert_called_once_with("item-1")
    assert len(results[0]) == 2
    assert results[0][0]["discount_rule_uuid"] == "dr-1"
    assert results[0][1]["rule"] == "B"


# ============================================================================
# MAIN ENTRY POINT FOR DIRECT EXECUTION
# ============================================================================

if __name__ == "__main__":
    """
    Run batch loader tests directly with Python for debugging and development.

    Usage:
        python test_batch_loaders.py              # Run all batch loader tests
        python test_batch_loaders.py -v           # Verbose output
        python test_batch_loaders.py -k test_item # Run specific test
        python test_batch_loaders.py -s           # Show print statements

    Examples:
        python test_batch_loaders.py -v
        python test_batch_loaders.py -k "test_item_loader" -s
    """
    import sys

    # Run pytest with this file
    sys.exit(pytest.main([__file__, "-v"] + sys.argv[1:]))
