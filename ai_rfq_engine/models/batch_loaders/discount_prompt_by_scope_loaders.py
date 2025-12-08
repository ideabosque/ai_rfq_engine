#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List

from promise import Promise
from silvaengine_utility.cache import HybridCacheEngine

from ...handlers.config import Config
from .base import Key, SafeDataLoader, normalize_model


class DiscountPromptGlobalLoader(SafeDataLoader):
    """
    Batch loader returning ACTIVE GLOBAL discount prompts.

    Usage:
        loaders.discount_prompt_global_loader.load(endpoint_id)

    Returns:
        List of active discount prompts with scope GLOBAL for the given endpoint
    """

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(DiscountPromptGlobalLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "discount_prompt")
            )
            cache_meta = Config.get_cache_entity_config().get("discount_prompt")
            self.cache_func_prefix = ""
            if cache_meta:
                self.cache_func_prefix = ".".join(
                    [cache_meta.get("module"), "get_global_discount_prompts"]
                )

    def generate_cache_key(self, key: Key) -> str:
        # Key is just endpoint_id
        key_data = ":".join([str(key)] + [str({})])
        return self.cache._generate_key(self.cache_func_prefix, key_data)

    def get_cache_data(self, key: Key) -> List[Dict[str, Any]] | None:
        cache_key = self.generate_cache_key(key)
        cached_item = self.cache.get(cache_key)
        if cached_item is None:
            return None
        if isinstance(cached_item, list):
            return [normalize_model(item) for item in cached_item]
        return [normalize_model(cached_item)]

    def set_cache_data(self, key: Key, data: Any) -> None:
        cache_key = self.generate_cache_key(key)
        self.cache.set(cache_key, data, ttl=Config.get_cache_ttl())

    def batch_load_fn(self, keys: List[str]) -> Promise:
        from ..discount_prompt import get_global_discount_prompts

        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[str, List[Dict[str, Any]]] = {}
        uncached_keys: List[str] = []

        if self.cache_enabled:
            for key in unique_keys:
                cached = self.get_cache_data(key)
                if cached is not None:
                    key_map[key] = cached
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        for endpoint_id in uncached_keys:
            try:
                # Load GLOBAL prompts for this endpoint
                global_prompts = get_global_discount_prompts(endpoint_id)
                normalized = [normalize_model(p) for p in global_prompts]
                if self.cache_enabled:
                    self.set_cache_data(endpoint_id, normalized)
                key_map[endpoint_id] = normalized
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[endpoint_id] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])


class DiscountPromptBySegmentLoader(SafeDataLoader):
    """
    Batch loader returning ACTIVE discount prompts for segments with hierarchical scopes.

    Usage:
        loaders.discount_prompt_by_segment_loader.load((endpoint_id, segment_uuid))

    Returns:
        List of active discount prompts with scopes GLOBAL + SEGMENT for the given segment
    """

    def __init__(self, logger=None, cache_enabled=True, global_loader=None, **kwargs):
        super(DiscountPromptBySegmentLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        self.global_loader = global_loader
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "discount_prompt")
            )
            cache_meta = Config.get_cache_entity_config().get("discount_prompt")
            self.cache_func_prefix = ""
            if cache_meta:
                self.cache_func_prefix = ".".join(
                    [cache_meta.get("module"), "get_discount_prompts_by_segment"]
                )

    def generate_cache_key(self, key: Key) -> str:
        # Key is (endpoint_id, segment_uuid)
        key_data = ":".join([str(k) for k in key] + [str({})])
        return self.cache._generate_key(self.cache_func_prefix, key_data)

    def get_cache_data(self, key: Key) -> List[Dict[str, Any]] | None:
        cache_key = self.generate_cache_key(key)
        cached_item = self.cache.get(cache_key)
        if cached_item is None:
            return None
        if isinstance(cached_item, list):
            return [normalize_model(item) for item in cached_item]
        return [normalize_model(cached_item)]

    def set_cache_data(self, key: Key, data: Any) -> None:
        cache_key = self.generate_cache_key(key)
        self.cache.set(cache_key, data, ttl=Config.get_cache_ttl())

    def batch_load_fn(self, keys: List[tuple]) -> Promise:
        from ..discount_prompt import get_discount_prompts_by_segment

        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[tuple, List[Dict[str, Any]]] = {}
        uncached_keys: List[tuple] = []

        if self.cache_enabled:
            for key in unique_keys:
                cached = self.get_cache_data(key)
                if cached is not None:
                    key_map[key] = cached
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        # Collect unique endpoint_ids to batch load GLOBAL prompts
        unique_endpoint_ids = list(set(endpoint_id for endpoint_id, _ in uncached_keys))

        # Use the global loader passed via constructor
        global_loader = self.global_loader

        def process_with_globals(global_prompts_by_endpoint):
            """Process segment prompts after GLOBAL prompts are loaded."""
            for endpoint_id, segment_uuid in uncached_keys:
                try:
                    # Get GLOBAL prompts for this endpoint
                    global_prompts = global_prompts_by_endpoint.get(endpoint_id, [])

                    # Load SEGMENT-specific prompts
                    segment_prompts = get_discount_prompts_by_segment(endpoint_id, segment_uuid)

                    # Combine GLOBAL + SEGMENT prompts
                    all_prompts = global_prompts + [normalize_model(p) for p in segment_prompts]

                    if self.cache_enabled:
                        self.set_cache_data((endpoint_id, segment_uuid), all_prompts)
                    key_map[(endpoint_id, segment_uuid)] = all_prompts
                except Exception as exc:  # pragma: no cover - defensive
                    if self.logger:
                        self.logger.exception(exc)
                    key_map[(endpoint_id, segment_uuid)] = []

            return [key_map.get(key, []) for key in keys]

        if global_loader and unique_endpoint_ids:
            # Load GLOBAL prompts for all unique endpoints in parallel
            return Promise.all([
                global_loader.load(endpoint_id) for endpoint_id in unique_endpoint_ids
            ]).then(lambda global_results: process_with_globals(
                dict(zip(unique_endpoint_ids, global_results))
            ))
        else:
            # Fallback: no global prompts
            return Promise.resolve(process_with_globals({}))


class DiscountPromptByItemLoader(SafeDataLoader):
    """
    Batch loader returning ACTIVE discount prompts for items with hierarchical scopes.

    Usage:
        loaders.discount_prompt_by_item_loader.load((endpoint_id, item_uuid))

    Returns:
        List of active discount prompts with scopes GLOBAL + ITEM for the given item
        Note: SEGMENT scope is not included as segment_uuid is not available at this level
    """

    def __init__(self, logger=None, cache_enabled=True, global_loader=None, **kwargs):
        super(DiscountPromptByItemLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        self.global_loader = global_loader
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "discount_prompt")
            )
            cache_meta = Config.get_cache_entity_config().get("discount_prompt")
            self.cache_func_prefix = ""
            if cache_meta:
                self.cache_func_prefix = ".".join(
                    [cache_meta.get("module"), "get_discount_prompts_by_item"]
                )

    def generate_cache_key(self, key: Key) -> str:
        key_data = ":".join([str(k) for k in key] + [str({})])
        return self.cache._generate_key(self.cache_func_prefix, key_data)

    def get_cache_data(self, key: Key) -> List[Dict[str, Any]] | None:
        cache_key = self.generate_cache_key(key)
        cached_item = self.cache.get(cache_key)
        if cached_item is None:
            return None
        if isinstance(cached_item, list):
            return [normalize_model(item) for item in cached_item]
        return [normalize_model(cached_item)]

    def set_cache_data(self, key: Key, data: Any) -> None:
        cache_key = self.generate_cache_key(key)
        self.cache.set(cache_key, data, ttl=Config.get_cache_ttl())

    def batch_load_fn(self, keys: List[tuple]) -> Promise:
        from ..discount_prompt import get_discount_prompts_by_item

        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[tuple, List[Dict[str, Any]]] = {}
        uncached_keys: List[tuple] = []

        if self.cache_enabled:
            for key in unique_keys:
                cached = self.get_cache_data(key)
                if cached is not None:
                    key_map[key] = cached
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        # Collect unique endpoint_ids to batch load GLOBAL prompts
        unique_endpoint_ids = list(set(endpoint_id for endpoint_id, _ in uncached_keys))

        # Use the global loader passed via constructor
        global_loader = self.global_loader

        def process_with_globals(global_prompts_by_endpoint):
            """Process item prompts after GLOBAL prompts are loaded."""
            for endpoint_id, item_uuid in uncached_keys:
                try:
                    # Get GLOBAL prompts for this endpoint
                    global_prompts = global_prompts_by_endpoint.get(endpoint_id, [])

                    # Load ITEM-specific prompts
                    item_prompts = get_discount_prompts_by_item(endpoint_id, item_uuid)

                    # Combine GLOBAL + ITEM prompts
                    all_prompts = global_prompts + [normalize_model(p) for p in item_prompts]

                    if self.cache_enabled:
                        self.set_cache_data((endpoint_id, item_uuid), all_prompts)
                    key_map[(endpoint_id, item_uuid)] = all_prompts
                except Exception as exc:  # pragma: no cover - defensive
                    if self.logger:
                        self.logger.exception(exc)
                    key_map[(endpoint_id, item_uuid)] = []

            return [key_map.get(key, []) for key in keys]

        if global_loader and unique_endpoint_ids:
            # Load GLOBAL prompts for all unique endpoints in parallel
            return Promise.all([
                global_loader.load(endpoint_id) for endpoint_id in unique_endpoint_ids
            ]).then(lambda global_results: process_with_globals(
                dict(zip(unique_endpoint_ids, global_results))
            ))
        else:
            # Fallback: no global prompts
            return Promise.resolve(process_with_globals({}))


class DiscountPromptByProviderItemLoader(SafeDataLoader):
    """
    Batch loader returning ACTIVE discount prompts for provider items with hierarchical scopes.

    Usage:
        loaders.discount_prompt_by_provider_item_loader.load((endpoint_id, item_uuid, provider_item_uuid))

    Returns:
        List of active discount prompts with scopes GLOBAL + PROVIDER_ITEM for the given provider item
        Note: SEGMENT and ITEM scopes are not included as segment_uuid is not available at this level
    """

    def __init__(self, logger=None, cache_enabled=True, global_loader=None, **kwargs):
        super(DiscountPromptByProviderItemLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        self.global_loader = global_loader
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "discount_prompt")
            )
            cache_meta = Config.get_cache_entity_config().get("discount_prompt")
            self.cache_func_prefix = ""
            if cache_meta:
                self.cache_func_prefix = ".".join(
                    [cache_meta.get("module"), "get_discount_prompts_by_provider_item"]
                )

    def generate_cache_key(self, key: Key) -> str:
        key_data = ":".join([str(k) for k in key] + [str({})])
        return self.cache._generate_key(self.cache_func_prefix, key_data)

    def get_cache_data(self, key: Key) -> List[Dict[str, Any]] | None:
        cache_key = self.generate_cache_key(key)
        cached_item = self.cache.get(cache_key)
        if cached_item is None:
            return None
        if isinstance(cached_item, list):
            return [normalize_model(item) for item in cached_item]
        return [normalize_model(cached_item)]

    def set_cache_data(self, key: Key, data: Any) -> None:
        cache_key = self.generate_cache_key(key)
        self.cache.set(cache_key, data, ttl=Config.get_cache_ttl())

    def batch_load_fn(self, keys: List[tuple]) -> Promise:
        from ..discount_prompt import get_discount_prompts_by_provider_item

        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[tuple, List[Dict[str, Any]]] = {}
        uncached_keys: List[tuple] = []

        if self.cache_enabled:
            for key in unique_keys:
                cached = self.get_cache_data(key)
                if cached is not None:
                    key_map[key] = cached
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        # Collect unique endpoint_ids to batch load GLOBAL prompts
        unique_endpoint_ids = list(set(endpoint_id for endpoint_id, _, _ in uncached_keys))

        # Use the global loader passed via constructor
        global_loader = self.global_loader

        def process_with_globals(global_prompts_by_endpoint):
            """Process provider item prompts after GLOBAL prompts are loaded."""
            for endpoint_id, item_uuid, provider_item_uuid in uncached_keys:
                try:
                    # Get GLOBAL prompts for this endpoint
                    global_prompts = global_prompts_by_endpoint.get(endpoint_id, [])

                    # Load PROVIDER_ITEM-specific prompts
                    provider_item_prompts = get_discount_prompts_by_provider_item(
                        endpoint_id, provider_item_uuid
                    )

                    # Combine GLOBAL + PROVIDER_ITEM prompts
                    all_prompts = global_prompts + [normalize_model(p) for p in provider_item_prompts]

                    if self.cache_enabled:
                        self.set_cache_data(
                            (endpoint_id, item_uuid, provider_item_uuid), all_prompts
                        )
                    key_map[(endpoint_id, item_uuid, provider_item_uuid)] = all_prompts
                except Exception as exc:  # pragma: no cover - defensive
                    if self.logger:
                        self.logger.exception(exc)
                    key_map[(endpoint_id, item_uuid, provider_item_uuid)] = []

            return [key_map.get(key, []) for key in keys]

        if global_loader and unique_endpoint_ids:
            # Load GLOBAL prompts for all unique endpoints in parallel
            return Promise.all([
                global_loader.load(endpoint_id) for endpoint_id in unique_endpoint_ids
            ]).then(lambda global_results: process_with_globals(
                dict(zip(unique_endpoint_ids, global_results))
            ))
        else:
            # Fallback: no global prompts
            return Promise.resolve(process_with_globals({}))
