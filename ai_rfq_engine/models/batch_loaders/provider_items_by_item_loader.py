#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List

from promise import Promise
from silvaengine_utility.cache import HybridCacheEngine

from ...handlers.config import Config
from ..provider_item import ProviderItemModel
from .base import Key, SafeDataLoader, normalize_model


class ProviderItemsByItemLoader(SafeDataLoader):
    """Batch loader returning provider items keyed by (endpoint_id, item_uuid)."""

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(ProviderItemsByItemLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "provider_item")
            )

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, List[Dict[str, Any]]] = {}
        uncached_keys: List[Key] = []

        if self.cache_enabled:
            for key in unique_keys:
                cache_key = f"{key[0]}:{key[1]}:list"  # endpoint_id:item_uuid:list
                cached_items = self.cache.get(cache_key)
                if cached_items is not None:
                    key_map[key] = cached_items
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        for endpoint_id, item_uuid in uncached_keys:
            try:
                provider_items = ProviderItemModel.item_uuid_index.query(
                    endpoint_id, ProviderItemModel.item_uuid == item_uuid
                )
                normalized = [normalize_model(pi) for pi in provider_items]
                key_map[(endpoint_id, item_uuid)] = normalized

                if self.cache_enabled:
                    cache_key = f"{endpoint_id}:{item_uuid}:list"
                    self.cache.set(cache_key, normalized, ttl=Config.get_cache_ttl())
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[(endpoint_id, item_uuid)] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])
