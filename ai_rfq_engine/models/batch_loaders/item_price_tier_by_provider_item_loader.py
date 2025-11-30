#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List

from promise import Promise
from silvaengine_utility.cache import HybridCacheEngine

from ...handlers.config import Config
from ..item_price_tier import ItemPriceTierModel
from .base import Key, SafeDataLoader, normalize_model


class ItemPriceTierByProviderItemLoader(SafeDataLoader):
    """
    Batch loader returning price tiers keyed by (item_uuid, provider_item_uuid).
    """

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(ItemPriceTierByProviderItemLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "item_price_tier")
            )

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, List[Dict[str, Any]]] = {}
        uncached_keys: List[Key] = []

        if self.cache_enabled:
            for key in unique_keys:
                cache_key = f"{key[0]}:{key[1]}"  # item_uuid:provider_item_uuid
                cached_tiers = self.cache.get(cache_key)
                if cached_tiers is not None:
                    key_map[key] = cached_tiers
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        for item_uuid, provider_item_uuid in uncached_keys:
            try:
                tiers = ItemPriceTierModel.provider_item_uuid_index.query(
                    item_uuid, ItemPriceTierModel.provider_item_uuid == provider_item_uuid
                )
                normalized = [normalize_model(tier) for tier in tiers]
                key_map[(item_uuid, provider_item_uuid)] = normalized

                if self.cache_enabled:
                    cache_key = f"{item_uuid}:{provider_item_uuid}"
                    self.cache.set(cache_key, normalized, ttl=Config.get_cache_ttl())
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[(item_uuid, provider_item_uuid)] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])
