#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Unit tests for batch loaders (DataLoader implementations)."""
from __future__ import annotations

__author__ = "bibow"

import sys
import os
from unittest.mock import MagicMock, patch

import pytest
from promise import Promise

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
    loader = ItemLoader(logger=context["logger"])

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
    loader = ProviderItemLoader(logger=context["logger"])

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
    loader = SegmentLoader(logger=context["logger"])

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
    loader = RequestLoader(logger=context["logger"])

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
    loader = QuoteLoader(logger=context["logger"])

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
    loader = ItemLoader(logger=context["logger"])

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
    loader = ItemLoader(logger=context["logger"])

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
    assert hasattr(loaders, "segment_loader")
    assert hasattr(loaders, "request_loader")
    assert hasattr(loaders, "quote_loader")

    # Verify each loader has correct type
    from ai_rfq_engine.models.batch_loaders import (
        ItemLoader,
        ProviderItemLoader,
        SegmentLoader,
        RequestLoader,
        QuoteLoader,
    )

    assert isinstance(loaders.item_loader, ItemLoader)
    assert isinstance(loaders.provider_item_loader, ProviderItemLoader)
    assert isinstance(loaders.segment_loader, SegmentLoader)
    assert isinstance(loaders.request_loader, RequestLoader)
    assert isinstance(loaders.quote_loader, QuoteLoader)


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
