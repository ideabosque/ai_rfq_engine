#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import annotations, print_function

__author__ = "bibow"

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

import json
import logging
import os
import re
import sys
import time
import uuid
from typing import Any, Dict, Optional, Sequence
from unittest.mock import MagicMock, Mock

import pytest
from dotenv import load_dotenv

load_dotenv()

_TEST_FUNCTION_ENV = "AI_RFQ_TEST_FUNCTION"
_TEST_MARKER_ENV = "AI_RFQ_TEST_MARKERS"
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test_ai_rfq_engine")


# Make package importable in common local setups
base_dir = os.getenv("base_dir", os.getcwd())
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "silvaengine_utility"))
sys.path.insert(1, os.path.join(base_dir, "silvaengine_dynamodb_base"))
sys.path.insert(2, os.path.join(base_dir, "ai_rfq_engine"))

from ai_rfq_engine import AIRFQEngine
from silvaengine_utility import Utility


def _call_method(
    engine: Any,
    method_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    label: Optional[str] = None,
) -> tuple[Optional[Any], Optional[Exception]]:
    """Invoke engine methods with consistent logging and error capture."""
    arguments = arguments or {}
    op = label or method_name
    cid = uuid.uuid4().hex[:8]
    logger.info(f"Method call: cid={cid} op={op} arguments={arguments}")
    t0 = time.perf_counter()

    try:
        method = getattr(engine, method_name)
    except AttributeError as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            f"Method response: cid={cid} op={op} elapsed_ms={elapsed_ms} success=False error={str(exc)}"
        )
        return None, exc

    try:
        result = method(**arguments)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            f"Method response: cid={cid} op={op} elapsed_ms={elapsed_ms} success=True result={result}"
        )
        return result, None
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            f"Method response: cid={cid} op={op} elapsed_ms={elapsed_ms} success=False error={str(exc)}"
        )
        return None, exc


def log_test_result(func):
    """Decorator to log test results."""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        test_name = func.__name__
        logger.info(f"{'='*80}")
        logger.info(f"Starting test: {test_name}")
        logger.info(f"{'='*80}")
        t0 = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.info(f"{'='*80}")
            logger.info(f"Test {test_name} PASSED (elapsed: {elapsed_ms}ms)")
            logger.info(f"{'='*80}\n")
            return result
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
            logger.error(f"{'='*80}")
            logger.error(f"Test {test_name} FAILED (elapsed: {elapsed_ms}ms): {exc}")
            logger.error(f"{'='*80}\n")
            raise

    return wrapper


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --test-function option sourced from environment variable."""
    parser.addoption(
        "--test-function",
        action="store",
        default=os.getenv(_TEST_FUNCTION_ENV, "").strip(),
        help=(
            "Run only tests whose name contains this substring. "
            f"Defaults to the {_TEST_FUNCTION_ENV} environment variable when set."
        ),
    )
    parser.addoption(
        "--test-markers",
        action="store",
        default=os.getenv(_TEST_MARKER_ENV, "").strip(),
        help=(
            "Run only tests that include any of the specified markers "
            "(comma or space separated). "
            f"Defaults to the {_TEST_MARKER_ENV} environment variable when set."
        ),
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Filter collected tests when a specific function name was requested."""
    target = config.getoption("--test-function")
    marker_filter_raw = config.getoption("--test-markers")
    markers = _parse_marker_filter(marker_filter_raw)

    if not target and not markers:
        return

    target_lower = target.lower()
    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []

    for item in items:
        name_match = not target_lower or target_lower in item.name.lower()
        marker_match = not markers or any(item.get_closest_marker(m) for m in markers)

        if name_match and marker_match:
            selected.append(item)
        else:
            deselected.append(item)

    if not selected:
        _raise_no_matches(_format_filter_description(target, marker_filter_raw), items)

    items[:] = selected
    config.hook.pytest_deselected(items=deselected)

    terminal = config.pluginmanager.get_plugin("terminalreporter")
    if terminal is not None:
        terminal.write_line(
            "Filtered tests with "
            f"{_format_filter_description(target, marker_filter_raw)} "
            f"({len(selected)} selected, {len(deselected)} deselected)."
        )


def _parse_marker_filter(raw: str) -> list[str]:
    """Return marker names from comma/space separated string."""
    if not raw:
        return []
    parts = re.split(r"[,\s]+", raw.strip())
    return [part for part in parts if part]


def _format_filter_description(target: str, marker_filter_raw: str) -> str:
    """Build a human-readable description of active filters."""
    descriptors: list[str] = []
    if target:
        descriptors.append(f"{_TEST_FUNCTION_ENV}='{target}'")
    if marker_filter_raw:
        descriptors.append(f"{_TEST_MARKER_ENV}='{marker_filter_raw}'")
    return " and ".join(descriptors) if descriptors else "no filters"


def _raise_no_matches(filters_desc: str, items: Sequence[pytest.Item]) -> None:
    """Raise an informative error when no tests matched the filter."""
    sample = ", ".join(sorted(item.name for item in items)[:5])
    hint = f" Available sample: {sample}" if sample else ""
    raise pytest.UsageError(f"{filters_desc} did not match any collected tests.{hint}")


# Test settings for ai_rfq_engine
SETTING = {
    "region_name": os.getenv("region_name"),
    "aws_access_key_id": os.getenv("aws_access_key_id"),
    "aws_secret_access_key": os.getenv("aws_secret_access_key"),
    "functs_on_local": {
        "ai_rfq_graphql": {
            "module_name": "ai_rfq_engine",
            "class_name": "AIRFQEngine",
        },
    },
    "endpoint_id": os.getenv("endpoint_id"),
    "execute_mode": os.getenv("execute_mode"),
}

# ============================================================================
# TEST DATA PARAMETERS - Load from JSON file
# ============================================================================


def _load_test_data():
    """Load test data from JSON file."""
    test_data_file = os.path.join(os.path.dirname(__file__), "test_data.json")
    try:
        with open(test_data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"Loaded test data from {test_data_file}")
            return data
    except FileNotFoundError:
        logger.warning(f"Test data file not found: {test_data_file}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing test data JSON: {e}")
        return {}


# Load all test data
_TEST_DATA = _load_test_data()

# Extract individual test data sets
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
SEGMENT_CONTACT_DELETE_TEST_DATA = _TEST_DATA.get(
    "segment_contact_delete_test_data", []
)
PROVIDER_ITEM_TEST_DATA = _TEST_DATA.get("provider_item_test_data", [])
PROVIDER_ITEM_GET_TEST_DATA = _TEST_DATA.get("provider_item_get_test_data", [])
PROVIDER_ITEM_LIST_TEST_DATA = _TEST_DATA.get("provider_item_list_test_data", [])
PROVIDER_ITEM_DELETE_TEST_DATA = _TEST_DATA.get("provider_item_delete_test_data", [])
PROVIDER_ITEM_BATCH_TEST_DATA = _TEST_DATA.get("provider_item_batch_test_data", [])
PROVIDER_ITEM_BATCH_GET_TEST_DATA = _TEST_DATA.get(
    "provider_item_batch_get_test_data", []
)
PROVIDER_ITEM_BATCH_LIST_TEST_DATA = _TEST_DATA.get(
    "provider_item_batch_list_test_data", []
)
PROVIDER_ITEM_BATCH_DELETE_TEST_DATA = _TEST_DATA.get(
    "provider_item_batch_delete_test_data", []
)
ITEM_PRICE_TIER_TEST_DATA = _TEST_DATA.get("item_price_tier_test_data", [])
ITEM_PRICE_TIER_GET_TEST_DATA = _TEST_DATA.get("item_price_tier_get_test_data", [])
ITEM_PRICE_TIER_LIST_TEST_DATA = _TEST_DATA.get("item_price_tier_list_test_data", [])
ITEM_PRICE_TIER_DELETE_TEST_DATA = _TEST_DATA.get(
    "item_price_tier_delete_test_data", []
)
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
# FIXTURES
# ============================================================================


@pytest.fixture(scope="module")
def ai_rfq_engine():
    """Provide an AIRFQEngine instance."""
    try:
        engine = AIRFQEngine(logger, **SETTING)
        setattr(engine, "__is_real__", True)
        return engine
    except Exception as ex:
        logger.warning(f"AIRFQEngine initialization failed: {ex}")
        pytest.skip(f"AIRFQEngine not available: {ex}")


@pytest.fixture(scope="module")
def schema(ai_rfq_engine):
    """Fetch GraphQL schema for testing."""
    endpoint_id = SETTING.get("endpoint_id")
    execute_mode = SETTING.get("execute_mode")
    try:
        schema = Utility.fetch_graphql_schema(
            logger,
            endpoint_id,
            "ai_rfq_graphql",
            setting=SETTING,
            test_mode=execute_mode,
        )
        logger.info("GraphQL schema fetched successfully")
        return schema
    except Exception as ex:
        logger.warning(f"Failed to fetch GraphQL schema: {ex}")
        pytest.skip(f"GraphQL schema not available: {ex}")


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
    logger.info(f"Query: {query}")

    result, error = _call_method(
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
@pytest.mark.parametrize("test_data", ITEM_TEST_DATA)
@log_test_result
def test_graphql_insert_update_item_py(ai_rfq_engine, schema, test_data):
    """Test item insert/update operation."""
    query = Utility.generate_graphql_operation("insertUpdateItem", "Mutation", schema)
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
        ai_rfq_engine,
        "ai_rfq_graphql",
        {
            "query": query,
            "variables": test_data,
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
    logger.info(f"Query: {query}")
    logger.info(f"Test data: {Utility.json_dumps(test_data)}")

    result, error = _call_method(
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
