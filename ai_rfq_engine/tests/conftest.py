#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Pytest configuration and fixtures for AI RFQ Engine tests."""
from __future__ import annotations

__author__ = "bibow"

import json
import logging
import os
import re
import sys
from typing import Any, Dict, Sequence

import pytest
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test_ai_rfq_engine")

# Make package importable
base_dir = os.getenv("base_dir", os.getcwd())
sys.path.insert(0, base_dir)
sys.path.insert(0, os.path.join(base_dir, "silvaengine_utility"))
sys.path.insert(1, os.path.join(base_dir, "silvaengine_dynamodb_base"))
sys.path.insert(2, os.path.join(base_dir, "ai_rfq_engine"))

from ai_rfq_engine import AIRFQEngine
from silvaengine_utility import Utility

# Test settings
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
    "execute_mode": os.getenv("execute_mode", "local"),
}


@pytest.fixture(scope="module")
def ai_rfq_engine():
    """Provide an AIRFQEngine instance for testing.

    This fixture is module-scoped for efficiency - the engine
    is initialized once per test module.
    """
    try:
        engine = AIRFQEngine(logger, **SETTING)
        # Mark as real engine instance for validation
        setattr(engine, "__is_real__", True)
        logger.info("AIRFQEngine initialized successfully")
        return engine
    except Exception as ex:
        logger.warning(f"AIRFQEngine initialization failed: {ex}")
        pytest.skip(f"AIRFQEngine not available: {ex}")


@pytest.fixture(scope="module")
def schema(ai_rfq_engine):
    """Fetch GraphQL schema for testing.

    Depends on ai_rfq_engine fixture.
    """
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


@pytest.fixture(scope="module")
def test_data():
    """Load test data from JSON file."""
    test_data_file = os.path.join(os.path.dirname(__file__), "test_data.json")

    try:
        with open(test_data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"Loaded test data from {test_data_file}")
            return data
    except FileNotFoundError:
        logger.warning(f"Test data file not found: {test_data_file}")
        pytest.skip(f"Test data file not found: {test_data_file}")
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing test data JSON: {e}")
        pytest.skip(f"Invalid test data JSON: {e}")


# ============================================================================
# CUSTOM PYTEST HOOKS
# ============================================================================

# Environment variable names for test filtering
_TEST_FUNCTION_ENV = "AI_RFQ_TEST_FUNCTION"
_TEST_MARKER_ENV = "AI_RFQ_TEST_MARKERS"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command-line options for test filtering."""
    parser.addoption(
        "--test-function",
        action="store",
        default=os.getenv(_TEST_FUNCTION_ENV, "").strip(),
        help=(
            "Run only tests whose name exactly matches this string. "
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


def _parse_marker_filter(raw: str) -> list[str]:
    """Parse comma/space separated marker string into list."""
    if not raw:
        return []
    parts = re.split(r"[,\s]+", raw.strip())
    return [part for part in parts if part]


def _format_filter_description(target: str, marker_filter_raw: str) -> str:
    """Build human-readable description of active filters."""
    descriptors: list[str] = []
    if target:
        descriptors.append(f"{_TEST_FUNCTION_ENV}='{target}'")
    if marker_filter_raw:
        descriptors.append(f"{_TEST_MARKER_ENV}='{marker_filter_raw}'")
    return " and ".join(descriptors) if descriptors else "no filters"


def _raise_no_matches(filters_desc: str, items: Sequence[pytest.Item]) -> None:
    """Raise informative error when no tests matched filter."""
    sample = ", ".join(sorted(item.name for item in items)[:5])
    hint = f" Available sample: {sample}" if sample else ""
    raise pytest.UsageError(
        f"{filters_desc} did not match any collected tests.{hint}"
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """
    Filter collected tests based on --test-function and --test-markers options.

    This allows flexible test execution like:
        pytest --test-function test_graphql_insert_update_item_py
        pytest --test-markers "integration,unit"
        AI_RFQ_TEST_FUNCTION=test_initialization_with_valid_params_py pytest
    """
    target = config.getoption("--test-function")
    marker_filter_raw = config.getoption("--test-markers")
    markers = _parse_marker_filter(marker_filter_raw)

    if not target and not markers:
        return  # No filtering requested

    target_lower = target.lower()
    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []

    for item in items:
        # Extract function name without parameters
        test_func_name = item.name.split("[")[0].lower()

        # Check if name matches (exact match)
        name_match = not target_lower or test_func_name == target_lower

        # Check if any requested marker is present
        marker_match = not markers or any(
            item.get_closest_marker(m) for m in markers
        )

        if name_match and marker_match:
            selected.append(item)
        else:
            deselected.append(item)

    if not selected:
        _raise_no_matches(
            _format_filter_description(target, marker_filter_raw), items
        )

    items[:] = selected
    config.hook.pytest_deselected(items=deselected)

    # Log filter results
    terminal = config.pluginmanager.get_plugin("terminalreporter")
    if terminal is not None:
        terminal.write_line(
            f"Filtered tests with {_format_filter_description(target, marker_filter_raw)} "
            f"({len(selected)} selected, {len(deselected)} deselected)."
        )
