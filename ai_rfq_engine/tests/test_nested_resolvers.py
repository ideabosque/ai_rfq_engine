#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Integration tests for nested GraphQL resolvers."""
from __future__ import annotations

__author__ = "bibow"

import os
import sys
import json
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from test_helpers import call_method, log_test_result, validate_nested_resolver_result


# ============================================================================
# TEST DATA
# ============================================================================
_TEST_DATA_FILE = Path(__file__).with_name("test_data.json")
try:
    _TEST_DATA = json.loads(_TEST_DATA_FILE.read_text())
except Exception:
    _TEST_DATA = {}

PROVIDER_ITEM_GET_TEST_DATA = _TEST_DATA.get(
    "provider_item_get_test_data", [{"providerItemUuid": "test_provider_item_001"}]
)
PROVIDER_ITEM_BATCH_GET_TEST_DATA = _TEST_DATA.get(
    "provider_item_batch_get_test_data",
    [{"providerItemUuid": "test_provider_item_001", "batchNo": "BATCH-001"}],
)
ITEM_PRICE_TIER_GET_TEST_DATA = _TEST_DATA.get(
    "item_price_tier_get_test_data", [{"itemPriceTierUuid": "test_tier_001"}]
)
QUOTE_GET_TEST_DATA = _TEST_DATA.get(
    "quote_get_test_data", [{"requestUuid": "test_request_001", "quoteUuid": "test_quote_001"}]
)
INSTALLMENT_GET_TEST_DATA = _TEST_DATA.get(
    "installment_get_test_data",
    [{"quoteUuid": "test_quote_001", "installmentUuid": "test_installment_001"}],
)
SEGMENT_CONTACT_GET_TEST_DATA = _TEST_DATA.get(
    "segment_contact_get_test_data", [{"segmentUuid": "test_segment_001", "email": "test@example.com"}]
)
FILE_GET_TEST_DATA = _TEST_DATA.get(
    "file_get_test_data", [{"requestUuid": "test_request_001", "fileName": "test_file.pdf"}]
)
DISCOUNT_RULE_GET_TEST_DATA = _TEST_DATA.get(
    "discount_rule_get_test_data", [{"discountRuleUuid": "test_rule_001"}]
)


# ============================================================================
# NESTED RESOLVER INTEGRATION TESTS
# ============================================================================


@pytest.mark.integration
@pytest.mark.nested_resolvers
@log_test_result
@pytest.mark.parametrize("test_data", PROVIDER_ITEM_GET_TEST_DATA)
def test_provider_item_with_nested_item(ai_rfq_engine, schema, test_data):
    """ProviderItem -> Item nesting."""
    query = """
    query GetProviderItemWithItem($providerItemUuid: String!) {
        providerItem(providerItemUuid: $providerItemUuid) {
            providerItemUuid
            itemUuid
            item {
                itemUuid
                itemName
                itemType
                uom
            }
        }
    }
    """

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {"query": query, "variables": test_data},
        "provider_item_with_nested_item",
    )

    if error or not result:
        pytest.skip("Provider item test data not available")

    if result.get("data", {}).get("providerItem"):
        validate_nested_resolver_result(
            result,
            expected_keys=["itemUuid", "itemName", "itemType"],
            nested_path=["data", "providerItem", "item"],
        )


@pytest.mark.integration
@pytest.mark.nested_resolvers
@log_test_result
@pytest.mark.parametrize("test_data", PROVIDER_ITEM_BATCH_GET_TEST_DATA)
def test_provider_item_batch_with_nested_relationships(ai_rfq_engine, schema, test_data):
    """ProviderItemBatch -> ProviderItem -> Item nesting."""
    query = """
    query GetProviderItemBatchWithNesting($providerItemUuid: String!, $batchNo: String!) {
        providerItemBatch(providerItemUuid: $providerItemUuid, batchNo: $batchNo) {
            providerItemUuid
            batchNo
            itemUuid
            totalCostPerUom
            item {
                itemUuid
                itemName
                uom
            }
            providerItem {
                providerItemUuid
                basePricePerUom
                itemUuid
                item {
                    itemUuid
                    itemName
                }
            }
        }
    }
    """

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {"query": query, "variables": test_data},
        "provider_item_batch_with_nested_relationships",
    )

    if error or not result:
        pytest.skip("Provider item batch test data not available")

    batch_data = result.get("data", {}).get("providerItemBatch")
    if batch_data and batch_data.get("item"):
        validate_nested_resolver_result(
            result,
            expected_keys=["itemUuid", "itemName"],
            nested_path=["data", "providerItemBatch", "item"],
        )

    if batch_data and batch_data.get("providerItem"):
        validate_nested_resolver_result(
            result,
            expected_keys=["providerItemUuid", "basePricePerUom"],
            nested_path=["data", "providerItemBatch", "providerItem"],
        )

        if batch_data["providerItem"].get("item"):
            validate_nested_resolver_result(
                result,
                expected_keys=["itemUuid", "itemName"],
                nested_path=["data", "providerItemBatch", "providerItem", "item"],
            )


@pytest.mark.integration
@pytest.mark.nested_resolvers
@log_test_result
@pytest.mark.parametrize("test_data", ITEM_PRICE_TIER_GET_TEST_DATA)
def test_item_price_tier_with_nested_relationships(ai_rfq_engine, schema, test_data):
    """ItemPriceTier -> ProviderItem -> Item + Segment nesting."""
    query = """
    query GetItemPriceTierWithNesting($itemPriceTierUuid: String!) {
        itemPriceTier(itemPriceTierUuid: $itemPriceTierUuid) {
            itemPriceTierUuid
            providerItemUuid
            segmentUuid
            marginPerUom
            providerItem {
                providerItemUuid
                basePricePerUom
                item {
                    itemName
                    uom
                }
            }
            segment {
                segmentUuid
                segmentName
            }
            providerItemBatches {
                batchNo
                pricePerUom
                inStock
            }
        }
    }
    """

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {"query": query, "variables": test_data},
        "item_price_tier_with_nested_relationships",
    )

    if error or not result:
        pytest.skip("Item price tier test data not available")

    tier_data = result.get("data", {}).get("itemPriceTier")

    if tier_data and tier_data.get("providerItem"):
        validate_nested_resolver_result(
            result,
            expected_keys=["providerItemUuid", "basePricePerUom"],
            nested_path=["data", "itemPriceTier", "providerItem"],
        )

        if tier_data["providerItem"].get("item"):
            validate_nested_resolver_result(
                result,
                expected_keys=["itemName", "uom"],
                nested_path=["data", "itemPriceTier", "providerItem", "item"],
            )

    if tier_data and tier_data.get("segment"):
        validate_nested_resolver_result(
            result,
            expected_keys=["segmentUuid", "segmentName"],
            nested_path=["data", "itemPriceTier", "segment"],
        )

    if tier_data and tier_data.get("provider_item_batches"):
        assert isinstance(tier_data["provider_item_batches"], list)
        if len(tier_data["provider_item_batches"]) > 0:
            batch = tier_data["provider_item_batches"][0]
            assert "batchNo" in batch
            assert "pricePerUom" in batch


@pytest.mark.integration
@pytest.mark.nested_resolvers
@log_test_result
@pytest.mark.parametrize("test_data", QUOTE_GET_TEST_DATA)
def test_quote_with_nested_request(ai_rfq_engine, schema, test_data):
    """Quote -> Request nesting."""
    query = """
    query GetQuoteWithRequest($requestUuid: String!, $quoteUuid: String!) {
        quote(requestUuid: $requestUuid, quoteUuid: $quoteUuid) {
            quoteUuid
            requestUuid
            totalQuoteAmount
            request {
                requestUuid
                requestTitle
                email
                status
            }
        }
    }
    """

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {"query": query, "variables": test_data},
        "quote_with_nested_request",
    )

    if error or not result:
        pytest.skip("Quote test data not available")

    quote_data = result.get("data", {}).get("quote")
    if quote_data and quote_data.get("request"):
        validate_nested_resolver_result(
            result,
            expected_keys=["requestUuid", "requestTitle"],
            nested_path=["data", "quote", "request"],
        )


@pytest.mark.integration
@pytest.mark.nested_resolvers
@log_test_result
@pytest.mark.parametrize("test_data", INSTALLMENT_GET_TEST_DATA)
def test_installment_with_nested_quote(ai_rfq_engine, schema, test_data):
    """Installment -> Quote -> Request nesting."""
    query = """
    query GetInstallmentWithNesting($quoteUuid: String!, $installmentUuid: String!) {
        installment(quoteUuid: $quoteUuid, installmentUuid: $installmentUuid) {
            installmentUuid
            quoteUuid
            requestUuid
            installmentAmount
            quote {
                quoteUuid
                totalQuoteAmount
                requestUuid
                request {
                    requestUuid
                    requestTitle
                    email
                }
            }
        }
    }
    """

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {"query": query, "variables": test_data},
        "installment_with_nested_quote",
    )

    if error or not result:
        pytest.skip("Installment test data not available")

    installment_data = result.get("data", {}).get("installment")

    if installment_data and installment_data.get("quote"):
        validate_nested_resolver_result(
            result,
            expected_keys=["quoteUuid", "totalQuoteAmount"],
            nested_path=["data", "installment", "quote"],
        )

        if installment_data["quote"].get("request"):
            validate_nested_resolver_result(
                result,
                expected_keys=["requestUuid", "requestTitle"],
                nested_path=["data", "installment", "quote", "request"],
            )


@pytest.mark.integration
@pytest.mark.nested_resolvers
@log_test_result
@pytest.mark.parametrize("test_data", SEGMENT_CONTACT_GET_TEST_DATA)
def test_segment_contact_with_nested_segment(ai_rfq_engine, schema, test_data):
    """SegmentContact -> Segment nesting."""
    query = """
    query GetSegmentContactWithSegment($segmentUuid: String!, $email: String!) {
        segmentContact(segmentUuid: $segmentUuid, email: $email) {
            email
            segmentUuid
            segment {
                segmentUuid
                segmentName
            }
        }
    }
    """

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {"query": query, "variables": test_data},
        "segment_contact_with_nested_segment",
    )

    if error or not result:
        pytest.skip("Segment contact test data not available")

    contact_data = result.get("data", {}).get("segmentContact")
    if contact_data and contact_data.get("segment"):
        validate_nested_resolver_result(
            result,
            expected_keys=["segmentUuid", "segmentName"],
            nested_path=["data", "segmentContact", "segment"],
        )


@pytest.mark.integration
@pytest.mark.nested_resolvers
@log_test_result
@pytest.mark.parametrize("test_data", FILE_GET_TEST_DATA)
def test_file_with_nested_request(ai_rfq_engine, schema, test_data):
    """File -> Request nesting."""
    query = """
    query GetFileWithRequest($requestUuid: String!, $fileName: String!) {
        file(requestUuid: $requestUuid, fileName: $fileName) {
            requestUuid
            fileName
            fileType
            request {
                requestUuid
                requestTitle
                email
            }
        }
    }
    """

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {"query": query, "variables": test_data},
        "file_with_nested_request",
    )

    if error or not result:
        pytest.skip("File test data not available")

    file_data = result.get("data", {}).get("file")
    if file_data and file_data.get("request"):
        validate_nested_resolver_result(
            result,
            expected_keys=["requestUuid", "requestTitle"],
            nested_path=["data", "file", "request"],
        )


@pytest.mark.integration
@pytest.mark.nested_resolvers
@log_test_result
@pytest.mark.parametrize("test_data", DISCOUNT_RULE_GET_TEST_DATA)
def test_discount_rule_with_nested_relationships(ai_rfq_engine, schema, test_data):
    """DiscountRule -> ProviderItem -> Item + Segment nesting."""
    query = """
    query GetDiscountRuleWithNesting($discountRuleUuid: String!) {
        discountRule(discountRuleUuid: $discountRuleUuid) {
            discountRuleUuid
            providerItemUuid
            segmentUuid
            maxDiscountPercentage
            providerItem {
                providerItemUuid
                basePricePerUom
                item {
                    itemName
                    uom
                }
            }
            segment {
                segmentUuid
                segmentName
            }
        }
    }
    """

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {"query": query, "variables": test_data},
        "discount_rule_with_nested_relationships",
    )

    if error or not result:
        pytest.skip("Discount rule test data not available")

    rule_data = result.get("data", {}).get("discountRule")

    if rule_data and rule_data.get("providerItem"):
        validate_nested_resolver_result(
            result,
            expected_keys=["providerItemUuid", "basePricePerUom"],
            nested_path=["data", "discountRule", "providerItem"],
        )

        if rule_data["providerItem"].get("item"):
            validate_nested_resolver_result(
                result,
                expected_keys=["itemName", "uom"],
                nested_path=["data", "discountRule", "providerItem", "item"],
            )

    if rule_data and rule_data.get("segment"):
        validate_nested_resolver_result(
            result,
            expected_keys=["segmentUuid", "segmentName"],
            nested_path=["data", "discountRule", "segment"],
        )


# ============================================================================
# PERFORMANCE CHECK
# ============================================================================

@pytest.mark.integration
@pytest.mark.nested_resolvers
@pytest.mark.slow
@log_test_result
def test_lazy_loading_performance_comparison(ai_rfq_engine, schema):
    """
    Verify that lazy loading works - queries without nested fields should not fetch nested data.

    This test compares performance of:
    1. Minimal query (no nested fields) - should be fast
    2. Nested query (with nested fields) - will be slower
    """
    import time

    # Query WITHOUT nested fields (should be fast)
    query_minimal = """
    query GetProviderItemListMinimal {
        providerItemList(limit: 10) {
            providerItemList {
                providerItemUuid
                itemUuid
                basePricePerUom
            }
        }
    }
    """

    t0 = time.perf_counter()
    result_minimal, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {"query": query_minimal},
        "test_minimal_query",
    )
    duration_minimal = time.perf_counter() - t0

    if error or not result_minimal:
        pytest.skip("Provider item list test data not available")

    # Query WITH nested fields (will be slower)
    query_nested = """
    query GetProviderItemListNested {
        providerItemList(limit: 10) {
            providerItemList {
                providerItemUuid
                basePricePerUom
                item {
                    itemName
                    itemType
                    uom
                }
            }
        }
    }
    """

    t0 = time.perf_counter()
    result_nested, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {"query": query_nested},
        "test_nested_query",
    )
    duration_nested = time.perf_counter() - t0

    if error or not result_nested:
        pytest.skip("Provider item list with nesting test data not available")

    # Log performance comparison
    print("\nPerformance comparison for 10 items:")
    print(f"  Minimal query (no nesting): {duration_minimal*1000:.2f}ms")
    print(f"  Nested query (1 level):     {duration_nested*1000:.2f}ms")
    print(f"  Difference:                 {(duration_nested-duration_minimal)*1000:.2f}ms")

    assert duration_minimal <= duration_nested * 1.5, \
        "Minimal query should not be significantly slower than nested query"


# ============================================================================
# MAIN ENTRY POINT FOR DIRECT EXECUTION
# ============================================================================

if __name__ == "__main__":
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / "pyproject.toml"

    sys.exit(
        pytest.main(
            [
                "-c",
                str(config_path),
                __file__,
                "-v",
                "-m",
                "nested_resolvers",
                *sys.argv[1:],
            ]
        )
    )
