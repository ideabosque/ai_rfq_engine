# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List

from promise import Promise
from silvaengine_utility.cache import HybridCacheEngine

from ...handlers.config import Config
from ..quote import QuoteModel
from .base import Key, SafeDataLoader, normalize_model


class QuoteLoader(SafeDataLoader):
    """Batch loader for QuoteModel keyed by (request_uuid, quote_uuid)."""

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(QuoteLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "quote")
            )

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, Dict[str, Any]] = {}
        uncached_keys = []

        if self.cache_enabled:
            for key in unique_keys:
                cache_key = f"{key[0]}:{key[1]}"  # request_uuid:quote_uuid
                cached_item = self.cache.get(cache_key)
                if cached_item:
                    key_map[key] = cached_item
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        if uncached_keys:
            try:
                for quote in QuoteModel.batch_get(uncached_keys):
                    normalized = normalize_model(quote)
                    key = (quote.request_uuid, quote.quote_uuid)
                    key_map[key] = normalized

                    if self.cache_enabled:
                        cache_key = f"{key[0]}:{key[1]}"
                        self.cache.set(
                            cache_key, normalized, ttl=Config.get_cache_ttl()
                        )

            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)

        return Promise.resolve([key_map.get(key) for key in keys])
