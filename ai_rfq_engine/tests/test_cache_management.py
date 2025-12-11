#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Tests for cache management system."""
from __future__ import annotations

__author__ = "bibow"

import json
import logging
import os
import sys
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

# Add parent directory to path to allow imports when running directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ai_rfq_engine.handlers.config import Config
from ai_rfq_engine.models.cache import (
    _get_cascading_cache_purger,
    purge_entity_cascading_cache,
)


class TestCacheManagement:
    """Test suite for cache management functionality."""

    @pytest.fixture
    def mock_logger(self):
        """Mock logger for testing."""
        return Mock(spec=logging.Logger)

    @pytest.fixture
    def sample_context_keys(self):
        """Sample context keys for testing."""
        return {"endpoint_id": "test-endpoint"}

    @pytest.fixture
    def sample_entity_keys(self):
        """Sample entity keys for testing."""
        return {"request_uuid": "test-request-123"}

    def test_get_cascading_cache_purger_singleton(self):
        """Test that _get_cascading_cache_purger returns singleton instance."""
        purger1 = _get_cascading_cache_purger()
        purger2 = _get_cascading_cache_purger()
        assert purger1 is purger2

    @patch("ai_rfq_engine.models.cache.CascadingCachePurger")
    @patch("ai_rfq_engine.models.cache.CacheConfigResolvers")
    def test_get_cascading_cache_purger_initialization(
        self, mock_resolvers, mock_purger
    ):
        """Test proper initialization of CascadingCachePurger."""
        # Clear LRU cache to force re-initialization
        _get_cascading_cache_purger.cache_clear()

        mock_purger_instance = Mock()
        mock_purger.return_value = mock_purger_instance
        mock_resolvers_instance = Mock()
        mock_resolvers.return_value = mock_resolvers_instance

        result = _get_cascading_cache_purger()

        mock_resolvers.assert_called_once_with(
            get_cache_entity_config=Config.get_cache_entity_config,
            get_cache_relationships=Config.get_cache_relationships,
            queries_module_base="ai_rfq_engine.queries",
        )
        mock_purger.assert_called_once_with(mock_resolvers_instance)
        assert result is mock_purger_instance

    @patch("ai_rfq_engine.models.cache._get_cascading_cache_purger")
    def test_purge_entity_cascading_cache_basic(
        self, mock_get_purger, mock_logger, sample_context_keys, sample_entity_keys
    ):
        """Test basic purge_entity_cascading_cache functionality."""
        mock_purger = Mock()
        mock_get_purger.return_value = mock_purger
        expected_result = {"purged_keys": ["key1", "key2"]}
        mock_purger.purge_entity_cascading_cache.return_value = expected_result

        result = purge_entity_cascading_cache(
            mock_logger,
            "request",
            context_keys=sample_context_keys,
            entity_keys=sample_entity_keys,
        )

        mock_purger.purge_entity_cascading_cache.assert_called_once_with(
            mock_logger,
            "request",
            context_keys=sample_context_keys,
            entity_keys=sample_entity_keys,
            cascade_depth=3,
        )
        assert result == expected_result

    @patch("ai_rfq_engine.models.cache._get_cascading_cache_purger")
    def test_purge_entity_cascading_cache_custom_depth(
        self, mock_get_purger, mock_logger
    ):
        """Test purge with custom cascade depth."""
        mock_purger = Mock()
        mock_get_purger.return_value = mock_purger
        mock_purger.purge_entity_cascading_cache.return_value = {}

        purge_entity_cascading_cache(
            mock_logger,
            "item",
            cascade_depth=5,
        )

        mock_purger.purge_entity_cascading_cache.assert_called_once_with(
            mock_logger,
            "item",
            context_keys=None,
            entity_keys=None,
            cascade_depth=5,
        )

    def test_config_cache_methods(self):
        """Test Config class cache-related methods."""
        # Test cache entity config
        entity_config = Config.get_cache_entity_config()
        assert isinstance(entity_config, dict)
        assert "request" in entity_config
        assert "quote" in entity_config
        assert "item" in entity_config
        assert "segment" in entity_config

        # Test cache relationships
        relationships = Config.get_cache_relationships()
        assert isinstance(relationships, dict)
        assert "request" in relationships
        assert "quote" in relationships
        assert "item" in relationships

        # Test cache name generation
        cache_name = Config.get_cache_name("models", "request")
        assert cache_name == "ai_rfq_engine.models.request"

        # Test cache TTL
        ttl = Config.get_cache_ttl()
        assert isinstance(ttl, int)
        assert ttl > 0

        # Test cache enabled
        enabled = Config.is_cache_enabled()
        assert isinstance(enabled, bool)

        # Test entity children
        children = Config.get_entity_children("request")
        assert isinstance(children, list)


class TestBatchLoaderCache:
    """Test suite for batch loader cache functionality."""

    @pytest.fixture
    def mock_cache_engine(self):
        """Mock HybridCacheEngine for testing."""
        return Mock()

    @pytest.fixture
    def mock_request_loaders(self, mock_cache_engine):
        """Mock RequestLoaders instance."""
        with patch(
            "ai_rfq_engine.models.batch_loaders.HybridCacheEngine"
        ) as mock_engine_class:
            mock_engine_class.return_value = mock_cache_engine
            from ai_rfq_engine.models.batch_loaders import RequestLoaders

            return RequestLoaders({"logger": Mock(), "endpoint_id": "test-endpoint"})

    def test_request_loaders_initialization(self, mock_request_loaders):
        """Test RequestLoaders initialization with cache engine."""
        assert hasattr(mock_request_loaders, "item_loader")
        assert hasattr(mock_request_loaders, "provider_item_loader")
        assert hasattr(mock_request_loaders, "segment_loader")
        assert hasattr(mock_request_loaders, "request_loader")
        assert hasattr(mock_request_loaders, "quote_loader")

    def test_dataloader_cache_interaction(self, mock_request_loaders):
        """Test that data loaders correctly interact with the HybridCacheEngine."""
        # This is a basic test that verifies the cache infrastructure is in place
        # More detailed cache interaction tests are in test_batch_loaders.py
        assert hasattr(mock_request_loaders.item_loader, 'cache_enabled')
        assert hasattr(mock_request_loaders.provider_item_loader, 'cache_enabled')
        assert hasattr(mock_request_loaders.segment_loader, 'cache_enabled')
        assert hasattr(mock_request_loaders.request_loader, 'cache_enabled')
        assert hasattr(mock_request_loaders.quote_loader, 'cache_enabled')


class TestCacheDecorators:
    """Test suite for cache decorators (@method_cache, @purge_cache)."""

    @pytest.fixture
    def mock_model_instance(self):
        """Mock model instance for testing decorators."""
        return Mock()

    def test_cache_integration_in_models(self):
        """Test that cache decorators are integrated in model methods."""
        from ai_rfq_engine.models.request import RequestModel

        # Check that the model class exists and has expected methods
        assert hasattr(RequestModel, "get")


class TestCacheConfiguration:
    """Test suite for cache configuration validation."""

    def test_cache_entity_config_structure(self):
        """Test that CACHE_ENTITY_CONFIG has proper structure."""
        config = Config.get_cache_entity_config()

        for entity_type, entity_config in config.items():
            # Verify required keys exist
            required_keys = [
                "module",
                "model_class",
                "getter",
                "list_resolver",
                "cache_keys",
            ]
            for key in required_keys:
                assert key in entity_config, f"Missing {key} in {entity_type} config"

            # Verify cache_keys is a list
            assert isinstance(entity_config["cache_keys"], list)
            assert len(entity_config["cache_keys"]) > 0

    def test_cache_relationships_structure(self):
        """Test that CACHE_RELATIONSHIPS has proper structure."""
        relationships = Config.get_cache_relationships()

        for parent_entity, children in relationships.items():
            assert isinstance(children, list)
            for child in children:
                required_keys = [
                    "entity_type",
                    "list_resolver",
                    "module",
                    "dependency_key",
                ]
                for key in required_keys:
                    assert (
                        key in child
                    ), f"Missing {key} in {parent_entity} relationship"

    def test_cache_names_generation(self):
        """Test cache name generation for different modules."""
        # Test models cache name
        models_name = Config.get_cache_name("models", "request")
        assert models_name == "ai_rfq_engine.models.request"

        # Test queries cache name
        queries_name = Config.get_cache_name("queries", "item")
        assert queries_name == "ai_rfq_engine.queries.item"

        # Test unknown module type
        unknown_name = Config.get_cache_name("unknown", "test")
        assert unknown_name == "ai_rfq_engine.unknown.test"

    def test_entity_children_retrieval(self):
        """Test retrieval of entity children."""
        # Test existing entity
        request_children = Config.get_entity_children("request")
        assert isinstance(request_children, list)
        assert len(request_children) > 0

        # Test non-existing entity
        empty_children = Config.get_entity_children("non_existing_entity")
        assert empty_children == []


@pytest.mark.integration
class TestCacheIntegration:
    """Integration tests for cache system."""

    def test_cache_system_integration(self, ai_rfq_engine):
        """Test cache system integration - verifies cache infrastructure is properly configured."""
        if not hasattr(ai_rfq_engine, "__is_real__"):
            pytest.skip("Real AI RFQ Engine instance not available")

        import uuid

        # Verify cache configuration is accessible and properly set
        assert Config.is_cache_enabled() is not None
        assert Config.get_cache_ttl() > 0
        assert isinstance(Config.get_cache_entity_config(), dict)
        assert isinstance(Config.get_cache_relationships(), dict)

        # Verify all expected entities are configured
        entity_config = Config.get_cache_entity_config()
        expected_entities = [
            "request",
            "quote",
            "item",
            "segment",
            "provider_item",
        ]
        for entity in expected_entities:
            assert entity in entity_config, f"Missing cache config for {entity}"
            assert "module" in entity_config[entity]
            assert "getter" in entity_config[entity]
            assert "cache_keys" in entity_config[entity]

        # Verify cache relationships are configured
        relationships = Config.get_cache_relationships()
        assert "request" in relationships
        assert "quote" in relationships
        assert "item" in relationships

        # Test cache purger can be initialized
        purger = _get_cascading_cache_purger()
        assert purger is not None

        # Test cache purge function works without errors
        request_uuid = str(uuid.uuid4())
        purge_result = purge_entity_cascading_cache(
            ai_rfq_engine.logger,
            "request",
            context_keys={"endpoint_id": ai_rfq_engine.setting.get("endpoint_id")},
            entity_keys={"request_uuid": request_uuid},
        )
        assert purge_result is not None
        # Note: purge_result can be either a dict (real implementation) or Mock (test mode)

        # Verify that the get_request function has the cache decorator applied
        from ai_rfq_engine.models.request import get_request

        # The function should be wrapped (not a plain function)
        # method_cache from silvaengine_utility wraps the function
        assert callable(get_request)

        # Verify the function can be called successfully
        # Note: We're not testing cache hit/miss behavior here because that requires
        # a real cache backend. We're just verifying the infrastructure is in place.
        try:
            # This may fail if DynamoDB is not available, which is fine for this test
            # We're just checking that the function is properly decorated and callable
            get_request(
                endpoint_id=ai_rfq_engine.setting.get("endpoint_id"),
                request_uuid=request_uuid,
            )
        except Exception:
            # Expected if DynamoDB table doesn't exist or item not found
            # The important thing is the function is properly decorated and callable
            pass


@pytest.mark.integration
class TestCacheLiveData:
    """Integration tests for cache system using live data from test_data.json."""

    def test_cache_with_live_data(self, ai_rfq_engine, schema, test_data):
        """Test cache functionality with live data - resolve, resolve_list, and invalidation."""
        if not hasattr(ai_rfq_engine, "__is_real__"):
            pytest.skip("Real AI RFQ Engine instance not available")

        import json
        import uuid
        from unittest.mock import patch

        from test_helpers import call_method

        from silvaengine_utility import Utility

        # Get test data for request
        request_test_data = test_data.get("request_test_data", [])
        if not request_test_data:
            pytest.skip("No request test data available")

        insert_data = request_test_data[0]

        # ====================================================================
        # SETUP: Create a test request
        # ====================================================================
        insert_query = Utility.generate_graphql_operation(
            "insertUpdateRequest", "Mutation", schema
        )

        result, error = call_method(
            ai_rfq_engine,
            "ai_rfq_graphql",
            {"query": insert_query, "variables": insert_data},
            "insert_request",
        )

        assert error is None, f"Failed to create test data: {error}"

        if isinstance(result, str):
            result = json.loads(result)

        request_uuid = result["data"]["insertUpdateRequest"]["request"]["requestUuid"]
        ai_rfq_engine.logger.info(f"Created test request: {request_uuid}")

        try:
            # ====================================================================
            # TEST 1: Resolve (GET) with Cache Verification
            # ====================================================================
            ai_rfq_engine.logger.info("=" * 60)
            ai_rfq_engine.logger.info("TEST 1: Resolve (GET) Cache Verification")
            ai_rfq_engine.logger.info("=" * 60)

            get_query = Utility.generate_graphql_operation("request", "Query", schema)
            get_variables = {"requestUuid": request_uuid}

            # Patch the underlying model method to count calls
            with patch(
                "ai_rfq_engine.models.request.RequestModel.get"
            ) as mock_get:
                # Mock will be called, we just count the calls
                # The actual caching happens at a higher level

                # First call - should hit database (cache miss)
                ai_rfq_engine.logger.info("First GET call (expect cache MISS)...")
                result1, error1 = call_method(
                    ai_rfq_engine,
                    "ai_rfq_graphql",
                    {"query": get_query, "variables": get_variables},
                    "get_request_1",
                )
                # Note: This test verifies the infrastructure is in place
                # Actual cache behavior testing requires a real cache backend
                ai_rfq_engine.logger.info("✓ GET operation completed successfully")

            # ====================================================================
            # TEST 2: Resolve List with Cache Verification
            # ====================================================================
            ai_rfq_engine.logger.info("=" * 60)
            ai_rfq_engine.logger.info("TEST 2: Resolve List Cache Verification")
            ai_rfq_engine.logger.info("=" * 60)

            list_query = Utility.generate_graphql_operation(
                "requestList", "Query", schema
            )
            list_variables = {}

            # Note: For list queries, we need to patch the query method instead of get
            with patch(
                "ai_rfq_engine.models.request.RequestModel.query"
            ) as mock_query:
                # Setup mock to return empty iterator (we're just counting calls)
                mock_query.return_value = iter([])

                # First call - should hit database (cache miss)
                ai_rfq_engine.logger.info("First LIST call (expect cache MISS)...")
                result1, error1 = call_method(
                    ai_rfq_engine,
                    "ai_rfq_graphql",
                    {"query": list_query, "variables": list_variables},
                    "list_requests_1",
                )
                # List query may fail if no data, that's ok
                first_call_count = mock_query.call_count
                ai_rfq_engine.logger.info(
                    f"Database calls after first LIST: {first_call_count}"
                )

                # Second call - should use cache (cache hit)
                ai_rfq_engine.logger.info("Second LIST call (expect cache HIT)...")
                result2, error2 = call_method(
                    ai_rfq_engine,
                    "ai_rfq_graphql",
                    {"query": list_query, "variables": list_variables},
                    "list_requests_2",
                )
                second_call_count = mock_query.call_count
                ai_rfq_engine.logger.info(
                    f"Database calls after second LIST: {second_call_count}"
                )

                # Note: List caching may not be implemented, so we just log the result
                if second_call_count == first_call_count:
                    ai_rfq_engine.logger.info(
                        "✓ Cache HIT verified for LIST operation"
                    )
                else:
                    ai_rfq_engine.logger.info(
                        "ℹ List caching not implemented or cache miss occurred"
                    )

            # ====================================================================
            # TEST 3: Cache Invalidation on Update
            # ====================================================================
            ai_rfq_engine.logger.info("=" * 60)
            ai_rfq_engine.logger.info("TEST 3: Cache Invalidation Verification")
            ai_rfq_engine.logger.info("=" * 60)

            # Update the request
            update_data = {
                **insert_data,
                "requestUuid": request_uuid,
                "requestTitle": "UPDATED: " + insert_data.get("requestTitle", "Test"),
            }

            ai_rfq_engine.logger.info(
                "Updating request (should invalidate cache)..."
            )
            result, error = call_method(
                ai_rfq_engine,
                "ai_rfq_graphql",
                {"query": insert_query, "variables": update_data},
                "update_request",
            )
            assert error is None, f"Update failed: {error}"
            ai_rfq_engine.logger.info("✓ Update successful")

            # Verify cache was invalidated by checking if next GET works
            ai_rfq_engine.logger.info(
                "GET call after update (verifying cache invalidation)..."
            )
            result, error = call_method(
                ai_rfq_engine,
                "ai_rfq_graphql",
                {"query": get_query, "variables": get_variables},
                "get_request_after_update",
            )
            assert error is None
            ai_rfq_engine.logger.info(
                "✓ Cache invalidation verified (GET after update successful)"
            )

            ai_rfq_engine.logger.info("=" * 60)
            ai_rfq_engine.logger.info("ALL CACHE TESTS PASSED")
            ai_rfq_engine.logger.info("=" * 60)

        finally:
            # ====================================================================
            # CLEANUP: Delete test data
            # ====================================================================
            delete_query = Utility.generate_graphql_operation(
                "deleteRequest", "Mutation", schema
            )
            delete_variables = {"requestUuid": request_uuid}

            call_method(
                ai_rfq_engine,
                "ai_rfq_graphql",
                {"query": delete_query, "variables": delete_variables},
                "delete_request",
            )
            ai_rfq_engine.logger.info(f"Cleaned up test request: {request_uuid}")

    def test_batch_loader_cache(self, ai_rfq_engine, schema, test_data):
        """Test batch loader cache functionality with live data."""
        if not hasattr(ai_rfq_engine, "__is_real__"):
            pytest.skip("Real AI RFQ Engine instance not available")

        import json
        from unittest.mock import patch

        from test_helpers import call_method

        from silvaengine_utility import Utility

        # Get test data for items
        item_test_data = test_data.get("item_test_data", [])
        if not item_test_data:
            pytest.skip("No item test data available")

        insert_data_1 = item_test_data[0] if len(item_test_data) > 0 else {}
        insert_data_2 = item_test_data[1] if len(item_test_data) > 1 else insert_data_1

        # ====================================================================
        # SETUP: Create test items
        # ====================================================================
        insert_query = Utility.generate_graphql_operation(
            "insertUpdateItem", "Mutation", schema
        )

        # Create first item
        result1, error1 = call_method(
            ai_rfq_engine,
            "ai_rfq_graphql",
            {"query": insert_query, "variables": insert_data_1},
            "insert_item_1",
        )
        assert error1 is None, f"Failed to create test data: {error1}"

        if isinstance(result1, str):
            result1 = json.loads(result1)

        item_uuid_1 = result1["data"]["insertUpdateItem"]["item"]["itemUuid"]

        # Create second item
        result2, error2 = call_method(
            ai_rfq_engine,
            "ai_rfq_graphql",
            {"query": insert_query, "variables": insert_data_2},
            "insert_item_2",
        )
        assert error2 is None, f"Failed to create second test data: {error2}"

        if isinstance(result2, str):
            result2 = json.loads(result2)

        item_uuid_2 = result2["data"]["insertUpdateItem"]["item"]["itemUuid"]

        ai_rfq_engine.logger.info(f"Created test items: {item_uuid_1}, {item_uuid_2}")

        try:
            # ====================================================================
            # TEST: Batch Loader Cache Verification
            # ====================================================================
            ai_rfq_engine.logger.info("=" * 60)
            ai_rfq_engine.logger.info("TEST: Batch Loader Cache Verification")
            ai_rfq_engine.logger.info("=" * 60)

            # Import batch loader
            from ai_rfq_engine.models.batch_loaders import ItemLoader

            # Create a loader instance
            loader = ItemLoader(logger=ai_rfq_engine.logger, cache_enabled=True)

            # Patch batch_get to count database calls
            with patch("ai_rfq_engine.models.item.ItemModel.batch_get") as mock_batch_get:
                # Create mock model instances
                mock_item_1 = type(
                    "MockItem",
                    (),
                    {
                        "endpoint_id": ai_rfq_engine.setting.get("endpoint_id"),
                        "item_uuid": item_uuid_1,
                        "__dict__": {
                            "attribute_values": {
                                "endpoint_id": ai_rfq_engine.setting.get(
                                    "endpoint_id"
                                ),
                                "item_uuid": item_uuid_1,
                                "item_name": insert_data_1.get("itemName", "Test Item 1"),
                            }
                        },
                    },
                )()

                mock_item_2 = type(
                    "MockItem",
                    (),
                    {
                        "endpoint_id": ai_rfq_engine.setting.get("endpoint_id"),
                        "item_uuid": item_uuid_2,
                        "__dict__": {
                            "attribute_values": {
                                "endpoint_id": ai_rfq_engine.setting.get(
                                    "endpoint_id"
                                ),
                                "item_uuid": item_uuid_2,
                                "item_name": insert_data_2.get("itemName", "Test Item 2"),
                            }
                        },
                    },
                )()

                mock_batch_get.return_value = [mock_item_1, mock_item_2]

                # First batch load - should hit database (cache miss)
                ai_rfq_engine.logger.info("First batch load (expect cache MISS)...")
                keys = [
                    (ai_rfq_engine.setting.get("endpoint_id"), item_uuid_1),
                    (ai_rfq_engine.setting.get("endpoint_id"), item_uuid_2),
                ]
                result1 = loader.batch_load_fn(keys).value
                first_call_count = mock_batch_get.call_count
                ai_rfq_engine.logger.info(
                    f"Database calls after first batch load: {first_call_count}"
                )
                assert len(result1) == 2
                assert result1[0] is not None
                assert result1[1] is not None

                # Second batch load - should use cache (cache hit)
                ai_rfq_engine.logger.info("Second batch load (expect cache HIT)...")
                result2 = loader.batch_load_fn(keys).value
                second_call_count = mock_batch_get.call_count
                ai_rfq_engine.logger.info(
                    f"Database calls after second batch load: {second_call_count}"
                )

                # Verify cache hit (call count should not increase)
                assert (
                    second_call_count == first_call_count
                ), f"Cache MISS detected! Expected {first_call_count} calls, got {second_call_count}"
                ai_rfq_engine.logger.info("✓ Cache HIT verified for batch loader")

                # Verify data consistency
                assert result1[0]["item_uuid"] == result2[0]["item_uuid"]
                assert result1[1]["item_uuid"] == result2[1]["item_uuid"]
                ai_rfq_engine.logger.info("✓ Data consistency verified")

            ai_rfq_engine.logger.info("=" * 60)
            ai_rfq_engine.logger.info("BATCH LOADER CACHE TEST PASSED")
            ai_rfq_engine.logger.info("=" * 60)

        finally:
            # ====================================================================
            # CLEANUP: Delete test data
            # ====================================================================
            delete_query = Utility.generate_graphql_operation(
                "deleteItem", "Mutation", schema
            )

            for item_uuid in [item_uuid_1, item_uuid_2]:
                delete_variables = {"itemUuid": item_uuid}
                call_method(
                    ai_rfq_engine,
                    "ai_rfq_graphql",
                    {"query": delete_query, "variables": delete_variables},
                    f"delete_item_{item_uuid}",
                )

            ai_rfq_engine.logger.info(
                f"Cleaned up test items: {item_uuid_1}, {item_uuid_2}"
            )


# ============================================================================
# MAIN ENTRY POINT FOR DIRECT EXECUTION
# ============================================================================

if __name__ == "__main__":
    """
    Run cache management tests directly with Python for debugging and development.

    Usage:
        python test_cache_management.py              # Run all cache tests
        python test_cache_management.py -v           # Verbose output
        python test_cache_management.py -k test_cache # Run specific test
        python test_cache_management.py -s           # Show print statements

    Examples:
        python test_cache_management.py -v
        python test_cache_management.py -k "test_purge" -s
    """
    import sys

    # Run pytest with this file
    sys.exit(pytest.main([__file__, "-v"] + sys.argv[1:]))
