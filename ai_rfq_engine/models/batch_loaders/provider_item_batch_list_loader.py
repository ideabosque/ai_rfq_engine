#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List

from promise import Promise
from silvaengine_utility.cache import HybridCacheEngine

from ...handlers.config import Config
from ..provider_item_batches import ProviderItemBatchModel
from .base import SafeDataLoader, normalize_model


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

    def batch_load_fn(self, keys: List[str]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[str, List[Dict[str, Any]]] = {}
        uncached_keys = []

        if self.cache_enabled:
            for key in unique_keys:
                cached_batches = self.cache.get(key)
                if cached_batches is not None:
                    key_map[key] = cached_batches
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        for provider_item_uuid in uncached_keys:
            try:
                batches = ProviderItemBatchModel.query(provider_item_uuid)
                normalized = [normalize_model(batch) for batch in batches]
                key_map[provider_item_uuid] = normalized

                if self.cache_enabled:
                    self.cache.set(
                        provider_item_uuid, normalized, ttl=Config.get_cache_ttl()
                    )
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[provider_item_uuid] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])
