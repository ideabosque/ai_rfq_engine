#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List

from promise import Promise
from silvaengine_utility.cache import HybridCacheEngine

from ...handlers.config import Config
from .base import SafeDataLoader, normalize_model, Key


class ProviderItemBatchListLoader(SafeDataLoader):
    """Batch loader returning batches for a provider item keyed by provider_item_uuid."""

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(ProviderItemBatchListLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "provider_item_batch")
            )
            cache_meta = Config.get_cache_entity_config().get("item_price_tier")
            self.cache_func_prefix = ""
            if cache_meta:
                self.cache_func_prefix = ".".join([cache_meta.get("module"), "get_provider_item_batches_by_provider_item"])

    def generate_cache_key(self, key: Key) -> str:
        key_data = ":".join([str(key), str({})])
        return self.cache._generate_key(
            self.cache_func_prefix,
            key_data
        )
    
    def get_cache_data(self, key: Key) -> Dict[str, Any] | None | List[Dict[str, Any]]:
        cache_key = self.generate_cache_key(key)
        cached_item = self.cache.get(cache_key)
        if cached_item is None:  # pragma: no cover - defensive
            return None
        if isinstance(cached_item, dict):  # pragma: no cover - defensive
            return cached_item
        if isinstance(cached_item, list):  # pragma: no cover - defensive
            return [normalize_model(item) for item in cached_item]
        return normalize_model(cached_item)

    def set_cache_data(self, key: Key, data: Any) -> None:
        cache_key = self.generate_cache_key(key)
        self.cache.set(cache_key, data, ttl=Config.get_cache_ttl())

    def batch_load_fn(self, keys: List[str]) -> Promise:
        from ..provider_item_batches import get_provider_item_batches_by_provider_item
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[str, List[Dict[str, Any]]] = {}
        uncached_keys = []

        if self.cache_enabled:
            for key in unique_keys:
                cached_batches = self.get_cache_data((key))
                if cached_batches is not None:
                    key_map[key] = cached_batches
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        for provider_item_uuid in uncached_keys:
            try:
                batches = get_provider_item_batches_by_provider_item(provider_item_uuid)
                if self.cache_enabled:
                    self.set_cache_data((provider_item_uuid), batches)
                normalized = [normalize_model(batch) for batch in batches]
                key_map[provider_item_uuid] = normalized

            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[provider_item_uuid] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])
