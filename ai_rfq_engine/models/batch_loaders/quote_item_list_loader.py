# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List

from promise import Promise
from silvaengine_utility.cache import HybridCacheEngine

from ...handlers.config import Config
from ..quote_item import QuoteItemModel
from .base import SafeDataLoader, normalize_model


class QuoteItemListLoader(SafeDataLoader):
    """Batch loader returning quote items keyed by quote_uuid."""

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(QuoteItemListLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "quote_item")
            )

    def batch_load_fn(self, keys: List[str]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[str, List[Dict[str, Any]]] = {}
        uncached_keys: List[str] = []

        if self.cache_enabled:
            for key in unique_keys:
                cached_items = self.cache.get(key)
                if cached_items is not None:
                    key_map[key] = cached_items
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        for quote_uuid in uncached_keys:
            try:
                items = QuoteItemModel.query(quote_uuid)
                normalized = [normalize_model(item) for item in items]
                key_map[quote_uuid] = normalized

                if self.cache_enabled:
                    self.cache.set(quote_uuid, normalized, ttl=Config.get_cache_ttl())
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[quote_uuid] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])
