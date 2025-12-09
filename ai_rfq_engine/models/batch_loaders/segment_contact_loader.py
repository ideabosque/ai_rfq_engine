#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List

from promise import Promise
from silvaengine_utility.cache import HybridCacheEngine

from ...handlers.config import Config
from .base import Key, SafeDataLoader, normalize_model


class SegmentContactLoader(SafeDataLoader):
    """
    Batch loader for segment_contact by (endpoint_id, email).

    Usage:
        loaders.segment_contact_loader.load((endpoint_id, email))

    Returns:
        Segment contact dict or None if not found
    """

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(SegmentContactLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "segment_contact")
            )
            cache_meta = Config.get_cache_entity_config().get("segment_contact")
            self.cache_func_prefix = ""
            if cache_meta:
                self.cache_func_prefix = ".".join(
                    [cache_meta.get("module"), "get_segment_contact"]
                )

    def generate_cache_key(self, key: Key) -> str:
        # Key is (endpoint_id, email)
        key_data = ":".join([str(k) for k in key])
        return self.cache._generate_key(self.cache_func_prefix, key_data)

    def get_cache_data(self, key: Key) -> Dict[str, Any] | None:
        cache_key = self.generate_cache_key(key)
        cached_item = self.cache.get(cache_key)
        if cached_item is None:
            return None
        if isinstance(cached_item, dict):
            return cached_item
        return normalize_model(cached_item)

    def set_cache_data(self, key: Key, data: Any) -> None:
        cache_key = self.generate_cache_key(key)
        self.cache.set(cache_key, data, ttl=Config.get_cache_ttl())

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        from ..segment_contact import SegmentContactModel

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

        # Load uncached segment_contacts from database
        for endpoint_id, email in uncached_keys:
            try:
                segment_contact = SegmentContactModel.get(endpoint_id, email)
                normalized = normalize_model(segment_contact)
                if self.cache_enabled:
                    self.set_cache_data((endpoint_id, email), normalized)
                key_map[(endpoint_id, email)] = normalized
            except SegmentContactModel.DoesNotExist:
                # Return None for non-existent segment contacts
                key_map[(endpoint_id, email)] = None
            except Exception as exc:
                if self.logger:
                    self.logger.exception(exc)
                key_map[(endpoint_id, email)] = None

        return Promise.resolve([key_map.get(key) for key in keys])
