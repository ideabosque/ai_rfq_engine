#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List

from promise import Promise
from silvaengine_utility.cache import HybridCacheEngine

from ...handlers.config import Config
from .base import Key, SafeDataLoader, normalize_model


class SegmentLoader(SafeDataLoader):
    """Batch loader for SegmentModel keyed by (partition_key, segment_uuid)."""

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(SegmentLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "segment")
            )
            cache_meta = Config.get_cache_entity_config().get("segment")
            self.cache_func_prefix = ""
            if cache_meta:
                self.cache_func_prefix = ".".join([cache_meta.get("module"), cache_meta.get("getter")])

    def generate_cache_key(self, key: Key) -> str:
        if not isinstance(key, tuple):
            key = (key,)
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

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        from ..segment import SegmentModel
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, Dict[str, Any]] = {}
        uncached_keys = []

        if self.cache_enabled:
            for key in unique_keys:
                cached_item = self.get_cache_data(key)
                if cached_item:
                    key_map[key] = cached_item
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        if uncached_keys:
            try:
                for segment in SegmentModel.batch_get(uncached_keys):
                    key = (segment.partition_key, segment.segment_uuid)

                    if self.cache_enabled:
                        self.set_cache_data(key, segment)
                    normalized = normalize_model(segment)
                    key_map[key] = normalized

            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)

        return Promise.resolve([key_map.get(key) for key in keys])
