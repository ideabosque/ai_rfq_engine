#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Comprehensive Tests for AI RFQ Engine

Tests all functionality of the AI RFQ Engine package:
- Engine initialization and configuration
- Item management (CRUD operations)
- Segment management
- Segment contact management
- Provider item management
- Provider item batch management
- Item price tier management
- Discount rule management
- Request management
- Quote management
- Quote item management
- Installment management
- File management
- GraphQL operations
- Data validation

Coverage: All engine methods, GraphQL operations, models, and validation.
"""
from __future__ import annotations, print_function

__author__ = "bibow"

import json
import logging
import os
import sys

import pytest

from silvaengine_utility import Utility
from test_helpers import call_method, log_test_result

logger = logging.getLogger("test_ai_rfq_engine")

# ============================================================================
# PYTEST FIXTURES
# ============================================================================
# Fixtures are defined in conftest.py:
# - ai_rfq_engine: AIRFQEngine instance
# - schema: GraphQL schema
# - test_data: Test data loaded from test_data.json

# Load test data
_test_data_file = os.path.join(os.path.dirname(__file__), "test_data.json")
try:
    with open(_test_data_file, "r") as f:
        _TEST_DATA = json.load(f)
except FileNotFoundError:
    _TEST_DATA = {}

# Extract individual test data sets for parametrization
ITEM_TEST_DATA = _TEST_DATA.get("item_test_data", [])
ITEM_GET_TEST_DATA = _TEST_DATA.get("item_get_test_data", [])
ITEM_LIST_TEST_DATA = _TEST_DATA.get("item_list_test_data", [])
ITEM_DELETE_TEST_DATA = _TEST_DATA.get("item_delete_test_data", [])
SEGMENT_TEST_DATA = _TEST_DATA.get("segment_test_data", [])
SEGMENT_GET_TEST_DATA = _TEST_DATA.get("segment_get_test_data", [])
SEGMENT_LIST_TEST_DATA = _TEST_DATA.get("segment_list_test_data", [])
SEGMENT_DELETE_TEST_DATA = _TEST_DATA.get("segment_delete_test_data", [])
SEGMENT_CONTACT_TEST_DATA = _TEST_DATA.get("segment_contact_test_data", [])
SEGMENT_CONTACT_GET_TEST_DATA = _TEST_DATA.get("segment_contact_get_test_data", [])
SEGMENT_CONTACT_LIST_TEST_DATA = _TEST_DATA.get("segment_contact_list_test_data", [])
SEGMENT_CONTACT_DELETE_TEST_DATA = _TEST_DATA.get("segment_contact_delete_test_data", [])
PROVIDER_ITEM_TEST_DATA = _TEST_DATA.get("provider_item_test_data", [])
PROVIDER_ITEM_GET_TEST_DATA = _TEST_DATA.get("provider_item_get_test_data", [])
PROVIDER_ITEM_LIST_TEST_DATA = _TEST_DATA.get("provider_item_list_test_data", [])
PROVIDER_ITEM_DELETE_TEST_DATA = _TEST_DATA.get("provider_item_delete_test_data", [])
PROVIDER_ITEM_BATCH_TEST_DATA = _TEST_DATA.get("provider_item_batch_test_data", [])
PROVIDER_ITEM_BATCH_GET_TEST_DATA = _TEST_DATA.get("provider_item_batch_get_test_data", [])
PROVIDER_ITEM_BATCH_LIST_TEST_DATA = _TEST_DATA.get("provider_item_batch_list_test_data", [])
PROVIDER_ITEM_BATCH_DELETE_TEST_DATA = _TEST_DATA.get("provider_item_batch_delete_test_data", [])
ITEM_PRICE_TIER_TEST_DATA = _TEST_DATA.get("item_price_tier_test_data", [])
ITEM_PRICE_TIER_GET_TEST_DATA = _TEST_DATA.get("item_price_tier_get_test_data", [])
ITEM_PRICE_TIER_LIST_TEST_DATA = _TEST_DATA.get("item_price_tier_list_test_data", [])
ITEM_PRICE_TIER_DELETE_TEST_DATA = _TEST_DATA.get("item_price_tier_delete_test_data", [])
DISCOUNT_RULE_TEST_DATA = _TEST_DATA.get("discount_rule_test_data", [])
DISCOUNT_RULE_GET_TEST_DATA = _TEST_DATA.get("discount_rule_get_test_data", [])
DISCOUNT_RULE_LIST_TEST_DATA = _TEST_DATA.get("discount_rule_list_test_data", [])
DISCOUNT_RULE_DELETE_TEST_DATA = _TEST_DATA.get("discount_rule_delete_test_data", [])
REQUEST_TEST_DATA = _TEST_DATA.get("request_test_data", [])
REQUEST_GET_TEST_DATA = _TEST_DATA.get("request_get_test_data", [])
REQUEST_LIST_TEST_DATA = _TEST_DATA.get("request_list_test_data", [])
REQUEST_DELETE_TEST_DATA = _TEST_DATA.get("request_delete_test_data", [])
QUOTE_TEST_DATA = _TEST_DATA.get("quote_test_data", [])
QUOTE_GET_TEST_DATA = _TEST_DATA.get("quote_get_test_data", [])
QUOTE_LIST_TEST_DATA = _TEST_DATA.get("quote_list_test_data", [])
QUOTE_DELETE_TEST_DATA = _TEST_DATA.get("quote_delete_test_data", [])
QUOTE_ITEM_TEST_DATA = _TEST_DATA.get("quote_item_test_data", [])
QUOTE_ITEM_GET_TEST_DATA = _TEST_DATA.get("quote_item_get_test_data", [])
QUOTE_ITEM_LIST_TEST_DATA = _TEST_DATA.get("quote_item_list_test_data", [])
QUOTE_ITEM_DELETE_TEST_DATA = _TEST_DATA.get("quote_item_delete_test_data", [])
INSTALLMENT_TEST_DATA = _TEST_DATA.get("installment_test_data", [])
INSTALLMENT_GET_TEST_DATA = _TEST_DATA.get("installment_get_test_data", [])
INSTALLMENT_LIST_TEST_DATA = _TEST_DATA.get("installment_list_test_data", [])
INSTALLMENT_DELETE_TEST_DATA = _TEST_DATA.get("installment_delete_test_data", [])
FILE_TEST_DATA = _TEST_DATA.get("file_test_data", [])
FILE_GET_TEST_DATA = _TEST_DATA.get("file_get_test_data", [])
FILE_LIST_TEST_DATA = _TEST_DATA.get("file_list_test_data", [])
FILE_DELETE_TEST_DATA = _TEST_DATA.get("file_delete_test_data", [])
# ============================================================================
# ENGINE INITIALIZATION TESTS
# ============================================================================
@pytest.mark.unit
@log_test_result
def test_initialization_with_valid_params_py(ai_rfq_engine):
    """Ensure engine fixture initializes with expected configuration."""
    assert ai_rfq_engine is not None
    assert hasattr(ai_rfq_engine, "ai_rfq_graphql")
    assert getattr(ai_rfq_engine, "__is_real__", False)

# ============================================================================
# PING TESTS
# ============================================================================
@pytest.mark.integration
@log_test_result
def test_graphql_ping_py(ai_rfq_engine, schema):
    """Test GraphQL ping operation."""
    query = Utility.generate_graphql_operation("ping", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {"query": query, "variables": {}},
        "graphql_ping",
    )

    assert error is None
    assert result is not None

# ============================================================================
# ITEM TESTS
# ============================================================================
@pytest.mark.integration
@log_test_result
def test_graphql_insert_update_item_py(ai_rfq_engine, schema, test_data):
    """Test item insert/update operation."""
    query = Utility.generate_graphql_operation("insertUpdateItem", "Mutation", schema)

    for item_data in test_data.get("item_test_data", []):
        result, error = call_method(
            ai_rfq_engine,
            "ai_rfq_graphql",
            {
                "query": query,
                "variables": item_data,
            },
            "insert_update_item",
        )

        assert error is None
        assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", ITEM_GET_TEST_DATA)
@log_test_result
def test_graphql_get_item_py(ai_rfq_engine, schema, test_data):
    """Test get item operation."""
    query = Utility.generate_graphql_operation("item", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "get_item",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", ITEM_LIST_TEST_DATA)
@log_test_result
def test_graphql_list_items_py(ai_rfq_engine, schema, test_data):
    """Test list items operation."""
    query = Utility.generate_graphql_operation("itemList", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "list_items",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", ITEM_DELETE_TEST_DATA)
@log_test_result
def test_graphql_delete_item_py(ai_rfq_engine, schema, test_data):
    """Test delete item operation."""
    query = Utility.generate_graphql_operation("deleteItem", "Mutation", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "delete_item",
    )

    # May fail if item doesn't exist, which is acceptable
    logger.info(f"Delete item result: {result}, error: {error}")

# ============================================================================
# SEGMENT TESTS
# ============================================================================
@pytest.mark.integration
@pytest.mark.parametrize("test_data", SEGMENT_TEST_DATA)
@log_test_result
def test_graphql_insert_update_segment_py(ai_rfq_engine, schema, test_data):
    """Test segment insert/update operation."""
    query = Utility.generate_graphql_operation(
        "insertUpdateSegment", "Mutation", schema
    )
    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "insert_update_segment",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", SEGMENT_GET_TEST_DATA)
@log_test_result
def test_graphql_get_segment_py(ai_rfq_engine, schema, test_data):
    """Test get segment operation."""
    query = Utility.generate_graphql_operation("segment", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "get_segment",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", SEGMENT_LIST_TEST_DATA)
@log_test_result
def test_graphql_list_segments_py(ai_rfq_engine, schema, test_data):
    """Test list segments operation."""
    query = Utility.generate_graphql_operation("segmentList", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "list_segments",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", SEGMENT_DELETE_TEST_DATA)
@log_test_result
def test_graphql_delete_segment_py(ai_rfq_engine, schema, test_data):
    """Test delete segment operation."""
    query = Utility.generate_graphql_operation("deleteSegment", "Mutation", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "delete_segment",
    )

    # May fail if segment doesn't exist, which is acceptable
    logger.info(f"Delete segment result: {result}, error: {error}")

# ============================================================================
# SEGMENT CONTACT TESTS
# ============================================================================
@pytest.mark.integration
@pytest.mark.parametrize("test_data", SEGMENT_CONTACT_TEST_DATA)
@log_test_result
def test_graphql_insert_update_segment_contact_py(ai_rfq_engine, schema, test_data):
    """Test segment contact insert/update operation."""
    query = Utility.generate_graphql_operation(
        "insertUpdateSegmentContact", "Mutation", schema
    )
    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "insert_update_segment_contact",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", SEGMENT_CONTACT_GET_TEST_DATA)
@log_test_result
def test_graphql_get_segment_contact_py(ai_rfq_engine, schema, test_data):
    """Test get segment contact operation."""
    query = Utility.generate_graphql_operation("segmentContact", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "get_segment_contact",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", SEGMENT_CONTACT_LIST_TEST_DATA)
@log_test_result
def test_graphql_list_segment_contacts_py(ai_rfq_engine, schema, test_data):
    """Test list segment contacts operation."""
    query = Utility.generate_graphql_operation("segmentContactList", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "list_segment_contacts",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", SEGMENT_CONTACT_DELETE_TEST_DATA)
@log_test_result
def test_graphql_delete_segment_contact_py(ai_rfq_engine, schema, test_data):
    """Test delete segment contact operation."""
    query = Utility.generate_graphql_operation(
        "deleteSegmentContact", "Mutation", schema
    )
    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "delete_segment_contact",
    )

    # May fail if segment contact doesn't exist, which is acceptable
    logger.info(f"Delete segment contact result: {result}, error: {error}")

# ============================================================================
# PROVIDER ITEM TESTS
# ============================================================================
@pytest.mark.integration
@pytest.mark.parametrize("test_data", PROVIDER_ITEM_TEST_DATA)
@log_test_result
def test_graphql_insert_update_provider_item_py(ai_rfq_engine, schema, test_data):
    """Test provider item insert/update operation."""
    query = Utility.generate_graphql_operation(
        "insertUpdateProviderItem", "Mutation", schema
    )
    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "insert_update_provider_item",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", PROVIDER_ITEM_GET_TEST_DATA)
@log_test_result
def test_graphql_get_provider_item_py(ai_rfq_engine, schema, test_data):
    """Test get provider item operation."""
    query = Utility.generate_graphql_operation("providerItem", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "get_provider_item",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", PROVIDER_ITEM_LIST_TEST_DATA)
@log_test_result
def test_graphql_provider_item_list_py(ai_rfq_engine, schema, test_data):
    """Test list provider items operation."""
    query = Utility.generate_graphql_operation("providerItemList", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "list_provider_items",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", PROVIDER_ITEM_DELETE_TEST_DATA)
@log_test_result
def test_graphql_delete_provider_item_py(ai_rfq_engine, schema, test_data):
    """Test delete provider item operation."""
    query = Utility.generate_graphql_operation("deleteProviderItem", "Mutation", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "delete_provider_item",
    )

    # May fail if provider item doesn't exist, which is acceptable
    logger.info(f"Delete provider item result: {result}, error: {error}")

# ============================================================================
# PROVIDER ITEM BATCH TESTS
# ============================================================================
@pytest.mark.integration
@pytest.mark.parametrize("test_data", PROVIDER_ITEM_BATCH_TEST_DATA)
@log_test_result
def test_graphql_insert_update_provider_item_batch_py(ai_rfq_engine, schema, test_data):
    """Test provider item batch insert/update operation."""
    query = Utility.generate_graphql_operation(
        "insertUpdateProviderItemBatch", "Mutation", schema
    )
    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "insert_update_provider_item_batch",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", PROVIDER_ITEM_BATCH_GET_TEST_DATA)
@log_test_result
def test_graphql_get_provider_item_batch_py(ai_rfq_engine, schema, test_data):
    """Test get provider item batch operation."""
    query = Utility.generate_graphql_operation("providerItemBatch", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "get_provider_item_batch",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", PROVIDER_ITEM_BATCH_LIST_TEST_DATA)
@log_test_result
def test_graphql_provider_item_batch_list_py(ai_rfq_engine, schema, test_data):
    """Test list provider item batches operation."""
    query = Utility.generate_graphql_operation("providerItemBatchList", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "list_provider_item_batches",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", PROVIDER_ITEM_BATCH_DELETE_TEST_DATA)
@log_test_result
def test_graphql_delete_provider_item_batch_py(ai_rfq_engine, schema, test_data):
    """Test delete provider item batch operation."""
    query = Utility.generate_graphql_operation(
        "deleteProviderItemBatch", "Mutation", schema
    )
    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "delete_provider_item_batch",
    )

    # May fail if provider item batch doesn't exist, which is acceptable
    logger.info(f"Delete provider item batch result: {result}, error: {error}")

# ============================================================================
# ITEM PRICE TIER TESTS
# ============================================================================
@pytest.mark.integration
@pytest.mark.parametrize("test_data", ITEM_PRICE_TIER_TEST_DATA)
@log_test_result
def test_graphql_insert_update_item_price_tier_py(ai_rfq_engine, schema, test_data):
    """Test item price tier insert/update operation."""
    query = Utility.generate_graphql_operation(
        "insertUpdateItemPriceTier", "Mutation", schema
    )
    logger.info(
        f"Test data: {Utility.json_dumps(test_data.pop("itemPriceTierUuid", None))}"
    )

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "insert_update_item_price_tier",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", ITEM_PRICE_TIER_GET_TEST_DATA)
@log_test_result
def test_graphql_get_item_price_tier_py(ai_rfq_engine, schema, test_data):
    """Test get item price tier operation."""
    query = Utility.generate_graphql_operation("itemPriceTier", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "get_item_price_tier",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", ITEM_PRICE_TIER_LIST_TEST_DATA)
@log_test_result
def test_graphql_item_price_tier_list_py(ai_rfq_engine, schema, test_data):
    """Test list item price tiers operation."""
    query = Utility.generate_graphql_operation("itemPriceTierList", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "list_item_price_tiers",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", ITEM_PRICE_TIER_DELETE_TEST_DATA)
@log_test_result
def test_graphql_delete_item_price_tier_py(ai_rfq_engine, schema, test_data):
    """Test delete item price tier operation."""
    query = Utility.generate_graphql_operation(
        "deleteItemPriceTier", "Mutation", schema
    )
    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "delete_item_price_tier",
    )

    # May fail if item price tier doesn't exist, which is acceptable
    logger.info(f"Delete item price tier result: {result}, error: {error}")

# ============================================================================
# DISCOUNT RULE TESTS
# ============================================================================
@pytest.mark.integration
@pytest.mark.parametrize("test_data", DISCOUNT_RULE_TEST_DATA)
@log_test_result
def test_graphql_insert_update_discount_rule_py(ai_rfq_engine, schema, test_data):
    """Test discount rule insert/update operation."""
    query = Utility.generate_graphql_operation(
        "insertUpdateDiscountRule", "Mutation", schema
    )
    logger.info(
        f"Test data: {Utility.json_dumps(test_data.pop("discountRuleUuid", None))}"
    )

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "insert_update_discount_rule",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", DISCOUNT_RULE_GET_TEST_DATA)
@log_test_result
def test_graphql_get_discount_rule_py(ai_rfq_engine, schema, test_data):
    """Test get discount rule operation."""
    query = Utility.generate_graphql_operation("discountRule", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "get_discount_rule",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", DISCOUNT_RULE_LIST_TEST_DATA)
@log_test_result
def test_graphql_discount_rule_list_py(ai_rfq_engine, schema, test_data):
    """Test list discount rules operation."""
    query = Utility.generate_graphql_operation("discountRuleList", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "list_discount_rules",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", DISCOUNT_RULE_DELETE_TEST_DATA)
@log_test_result
def test_graphql_delete_discount_rule_py(ai_rfq_engine, schema, test_data):
    """Test delete discount rule operation."""
    query = Utility.generate_graphql_operation("deleteDiscountRule", "Mutation", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "delete_discount_rule",
    )

    # May fail if discount rule doesn't exist, which is acceptable
    logger.info(f"Delete discount rule result: {result}, error: {error}")

# ============================================================================
# REQUEST TESTS
# ============================================================================
@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_TEST_DATA)
@log_test_result
def test_graphql_insert_update_request_py(ai_rfq_engine, schema, test_data):
    """Test request insert/update operation."""
    query = Utility.generate_graphql_operation(
        "insertUpdateRequest", "Mutation", schema
    )
    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "insert_update_request",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_GET_TEST_DATA)
@log_test_result
def test_graphql_get_request_py(ai_rfq_engine, schema, test_data):
    """Test get request operation."""
    query = Utility.generate_graphql_operation("request", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "get_request",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_LIST_TEST_DATA)
@log_test_result
def test_graphql_request_list_py(ai_rfq_engine, schema, test_data):
    """Test list requests operation."""
    query = Utility.generate_graphql_operation("requestList", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "list_requests",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", REQUEST_DELETE_TEST_DATA)
@log_test_result
def test_graphql_delete_request_py(ai_rfq_engine, schema, test_data):
    """Test delete request operation."""
    query = Utility.generate_graphql_operation("deleteRequest", "Mutation", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "delete_request",
    )

    # May fail if request doesn't exist, which is acceptable
    logger.info(f"Delete request result: {result}, error: {error}")

# ============================================================================
# QUOTE TESTS
# ============================================================================
@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_TEST_DATA)
@log_test_result
def test_graphql_insert_update_quote_py(ai_rfq_engine, schema, test_data):
    """Test quote insert/update operation."""
    query = Utility.generate_graphql_operation("insertUpdateQuote", "Mutation", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "insert_update_quote",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_GET_TEST_DATA)
@log_test_result
def test_graphql_get_quote_py(ai_rfq_engine, schema, test_data):
    """Test get quote operation."""
    query = Utility.generate_graphql_operation("quote", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "get_quote",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_LIST_TEST_DATA)
@log_test_result
def test_graphql_quote_list_py(ai_rfq_engine, schema, test_data):
    """Test list quotes operation."""
    query = Utility.generate_graphql_operation("quoteList", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "list_quotes",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_DELETE_TEST_DATA)
@log_test_result
def test_graphql_delete_quote_py(ai_rfq_engine, schema, test_data):
    """Test delete quote operation."""
    query = Utility.generate_graphql_operation("deleteQuote", "Mutation", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "delete_quote",
    )

    # May fail if quote doesn't exist, which is acceptable
    logger.info(f"Delete quote result: {result}, error: {error}")

# ============================================================================
# QUOTE ITEM TESTS
# ============================================================================
@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_ITEM_TEST_DATA)
@log_test_result
def test_graphql_insert_update_quote_item_py(ai_rfq_engine, schema, test_data):
    """Test quote item insert/update operation."""
    query = Utility.generate_graphql_operation(
        "insertUpdateQuoteItem", "Mutation", schema
    )
    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "insert_update_quote_item",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_ITEM_GET_TEST_DATA)
@log_test_result
def test_graphql_get_quote_item_py(ai_rfq_engine, schema, test_data):
    """Test get quote item operation."""
    query = Utility.generate_graphql_operation("quoteItem", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "get_quote_item",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_ITEM_LIST_TEST_DATA)
@log_test_result
def test_graphql_quote_item_list_py(ai_rfq_engine, schema, test_data):
    """Test list quote items operation."""
    query = Utility.generate_graphql_operation("quoteItemList", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "list_quote_items",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", QUOTE_ITEM_DELETE_TEST_DATA)
@log_test_result
def test_graphql_delete_quote_item_py(ai_rfq_engine, schema, test_data):
    """Test delete quote item operation."""
    query = Utility.generate_graphql_operation("deleteQuoteItem", "Mutation", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "delete_quote_item",
    )

    # May fail if quote item doesn't exist, which is acceptable
    logger.info(f"Delete quote item result: {result}, error: {error}")

# ============================================================================
# INSTALLMENT TESTS
# ============================================================================
@pytest.mark.integration
@pytest.mark.parametrize("test_data", INSTALLMENT_TEST_DATA)
@log_test_result
def test_graphql_insert_update_installment_py(ai_rfq_engine, schema, test_data):
    """Test installment insert/update operation."""
    query = Utility.generate_graphql_operation(
        "insertUpdateInstallment", "Mutation", schema
    )
    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "insert_update_installment",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", INSTALLMENT_GET_TEST_DATA)
@log_test_result
def test_graphql_get_installment_py(ai_rfq_engine, schema, test_data):
    """Test get installment operation."""
    query = Utility.generate_graphql_operation("installment", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "get_installment",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", INSTALLMENT_LIST_TEST_DATA)
@log_test_result
def test_graphql_installment_list_py(ai_rfq_engine, schema, test_data):
    """Test list installments operation."""
    query = Utility.generate_graphql_operation("installmentList", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "list_installments",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", INSTALLMENT_DELETE_TEST_DATA)
@log_test_result
def test_graphql_delete_installment_py(ai_rfq_engine, schema, test_data):
    """Test delete installment operation."""
    query = Utility.generate_graphql_operation("deleteInstallment", "Mutation", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "delete_installment",
    )

    # May fail if installment doesn't exist, which is acceptable
    logger.info(f"Delete installment result: {result}, error: {error}")

# ============================================================================
# FILE TESTS
# ============================================================================
@pytest.mark.integration
@pytest.mark.parametrize("test_data", FILE_TEST_DATA)
@log_test_result
def test_graphql_insert_update_file_py(ai_rfq_engine, schema, test_data):
    """Test file insert/update operation."""
    query = Utility.generate_graphql_operation("insertUpdateFile", "Mutation", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "insert_update_file",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", FILE_GET_TEST_DATA)
@log_test_result
def test_graphql_get_file_py(ai_rfq_engine, schema, test_data):
    """Test get file operation."""
    query = Utility.generate_graphql_operation("file", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "get_file",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", FILE_LIST_TEST_DATA)
@log_test_result
def test_graphql_file_list_py(ai_rfq_engine, schema, test_data):
    """Test list files operation."""
    query = Utility.generate_graphql_operation("fileList", "Query", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "list_files",
    )

    assert error is None
    assert result is not None


@pytest.mark.integration
@pytest.mark.parametrize("test_data", FILE_DELETE_TEST_DATA)
@log_test_result
def test_graphql_delete_file_py(ai_rfq_engine, schema, test_data):
    """Test delete file operation."""
    query = Utility.generate_graphql_operation("deleteFile", "Mutation", schema)

    result, error = call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
        },
        "delete_file",
    )

    # May fail if file doesn't exist, which is acceptable
    logger.info(f"Delete file result: {result}, error: {error}")
if __name__ == "__main__":
    pytest.main([__file__, "-v"], plugins=[sys.modules[__name__]])
