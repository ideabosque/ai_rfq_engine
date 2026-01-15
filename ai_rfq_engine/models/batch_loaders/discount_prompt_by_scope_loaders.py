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
        loaders.discount_prompt_global_loader.load(partition_key)

    Returns:
        List of active discount prompts with scope GLOBAL for the given partition
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
        # Key is just partition_key
        if not isinstance(key, tuple):
            key = (key,)
        key_data = ":".join([str(key)] + [str({})])
        return self.cache._generate_key(self.cache_func_prefix, key_data)

    def get_cache_data(self, key: Key) -> List[Dict[str, Any]] | None:
        cache_key = self.generate_cache_key(key)
        cached_item = self.cache.get(cache_key)
        if cached_item is None:
            return None
        if isinstance(cached_item, list):
            # Check if items are already dicts (from cache) or models
            return [
                item if isinstance(item, dict) else normalize_model(item)
                for item in cached_item
            ]
        # Single item case
        if isinstance(cached_item, dict):
            return [cached_item]
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

        for partition_key in uncached_keys:
            try:
                # Load GLOBAL prompts for this partition
                global_prompts = get_global_discount_prompts(partition_key)
                normalized = [normalize_model(p) for p in global_prompts]
                key_map[partition_key] = normalized
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[partition_key] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])


class DiscountPromptBySegmentLoader(SafeDataLoader):
    """
    Batch loader returning ACTIVE discount prompts for segments with hierarchical scopes.

    Usage:
        loaders.discount_prompt_by_segment_loader.load((partition_key, segment_uuid))

    Returns:
        List of active discount prompts with scopes GLOBAL + SEGMENT for the given segment
    """

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(DiscountPromptBySegmentLoader, self).__init__(
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
                    [cache_meta.get("module"), "get_discount_prompts_by_segment"]
                )

    def generate_cache_key(self, key: Key) -> str:
        # Key is (partition_key, segment_uuid)
        if not isinstance(key, tuple):
            key = (key,)
        key_data = ":".join([str(key)] + [str({})])
        return self.cache._generate_key(self.cache_func_prefix, key_data)

    def get_cache_data(self, key: Key) -> List[Dict[str, Any]] | None:
        cache_key = self.generate_cache_key(key)
        cached_item = self.cache.get(cache_key)
        if cached_item is None:
            return None
        if isinstance(cached_item, list):
            # Check if items are already dicts (from cache) or models
            return [
                item if isinstance(item, dict) else normalize_model(item)
                for item in cached_item
            ]
        # Single item case
        if isinstance(cached_item, dict):
            return [cached_item]
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

        for partition_key, segment_uuid in uncached_keys:
            try:
                # Load SEGMENT-specific prompts
                segment_prompts = get_discount_prompts_by_segment(
                    partition_key, segment_uuid
                )
                normalized = [normalize_model(p) for p in segment_prompts]
                # if self.cache_enabled:
                #     self.set_cache_data((partition_key, segment_uuid), normalized)
                key_map[(partition_key, segment_uuid)] = normalized
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[(partition_key, segment_uuid)] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])


class DiscountPromptByItemLoader(SafeDataLoader):
    """
    Batch loader returning ACTIVE discount prompts for items with hierarchical scopes.

    Usage:
        loaders.discount_prompt_by_item_loader.load((partition_key, item_uuid))

    Returns:
        List of active discount prompts with scopes GLOBAL + ITEM for the given item
        Note: SEGMENT scope is not included as segment_uuid is not available at this level
    """

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(DiscountPromptByItemLoader, self).__init__(
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
                    [cache_meta.get("module"), "get_discount_prompts_by_item"]
                )

    def generate_cache_key(self, key: Key) -> str:
        if not isinstance(key, tuple):
            key = (key,)
        key_data = ":".join([str(key)] + [str({})])
        return self.cache._generate_key(self.cache_func_prefix, key_data)

    def get_cache_data(self, key: Key) -> List[Dict[str, Any]] | None:
        cache_key = self.generate_cache_key(key)
        cached_item = self.cache.get(cache_key)
        if cached_item is None:
            return None
        if isinstance(cached_item, list):
            # Check if items are already dicts (from cache) or models
            return [
                item if isinstance(item, dict) else normalize_model(item)
                for item in cached_item
            ]
        # Single item case
        if isinstance(cached_item, dict):
            return [cached_item]
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

        for partition_key, item_uuid in uncached_keys:
            try:
                # Load ITEM-specific prompts
                item_prompts = get_discount_prompts_by_item(partition_key, item_uuid)

                # Combine GLOBAL + ITEM prompts
                normalized = [normalize_model(p) for p in item_prompts]
                # if self.cache_enabled:
                #     self.set_cache_data((partition_key, item_uuid), normalized)
                key_map[(partition_key, item_uuid)] = normalized
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[(partition_key, item_uuid)] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])


class DiscountPromptByProviderItemLoader(SafeDataLoader):
    """
    Batch loader returning ACTIVE discount prompts for provider items with hierarchical scopes.

    Usage:
        loaders.discount_prompt_by_provider_item_loader.load((partition_key, item_uuid, provider_item_uuid))

    Returns:
        List of active discount prompts with scopes GLOBAL + PROVIDER_ITEM for the given provider item
        Note: SEGMENT and ITEM scopes are not included as segment_uuid is not available at this level
    """

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(DiscountPromptByProviderItemLoader, self).__init__(
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
                    [cache_meta.get("module"), "get_discount_prompts_by_provider_item"]
                )

    def generate_cache_key(self, key: Key) -> str:
        if not isinstance(key, tuple):
            key = (key,)
        key_data = ":".join([str(key)] + [str({})])
        return self.cache._generate_key(self.cache_func_prefix, key_data)

    def get_cache_data(self, key: Key) -> List[Dict[str, Any]] | None:
        cache_key = self.generate_cache_key(key)
        cached_item = self.cache.get(cache_key)
        if cached_item is None:
            return None
        if isinstance(cached_item, list):
            # Check if items are already dicts (from cache) or models
            return [
                item if isinstance(item, dict) else normalize_model(item)
                for item in cached_item
            ]
        # Single item case
        if isinstance(cached_item, dict):
            return [cached_item]
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

        for partition_key, item_uuid, provider_item_uuid in uncached_keys:
            try:
                # Load PROVIDER_ITEM-specific prompts
                provider_item_prompts = get_discount_prompts_by_provider_item(
                    partition_key, provider_item_uuid
                )

                # Combine GLOBAL + PROVIDER_ITEM prompts
                normalized = [normalize_model(p) for p in provider_item_prompts]
                # if self.cache_enabled:
                #     self.set_cache_data(
                #         (partition_key, item_uuid, provider_item_uuid), normalized
                #     )
                key_map[(partition_key, item_uuid, provider_item_uuid)] = normalized
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[(partition_key, item_uuid, provider_item_uuid)] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])
