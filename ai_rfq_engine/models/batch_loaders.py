#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List, Tuple

from promise import Promise
from promise.dataloader import DataLoader
from silvaengine_utility import Utility
from silvaengine_utility.cache import HybridCacheEngine

from ..handlers.config import Config
from .item import ItemModel
from .provider_item import ProviderItemModel
from .quote import QuoteModel
from .request import RequestModel
from .segment import SegmentModel

# Type aliases for readability
Key = Tuple[str, str]


def _normalize_model(model: Any) -> Dict[str, Any]:
    """Safely convert a Pynamo model into a plain dict."""
    return Utility.json_normalize(model.__dict__["attribute_values"])


class _SafeDataLoader(DataLoader):
    """
    Base DataLoader that swallows and logs errors rather than breaking the entire
    request. This keeps individual load failures isolated.
    """

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(_SafeDataLoader, self).__init__(**kwargs)
        self.logger = logger
        self.cache_enabled = cache_enabled and Config.is_cache_enabled()

    def dispatch(self):
        try:
            return super(_SafeDataLoader, self).dispatch()
        except Exception as exc:  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception(exc)
            raise


class ItemLoader(_SafeDataLoader):
    """Batch loader for ItemModel records keyed by (endpoint_id, item_uuid)."""

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(ItemLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(Config.get_cache_name("models", "item"))

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, Dict[str, Any]] = {}
        uncached_keys = []

        # Check cache first if enabled
        if self.cache_enabled:
            for key in unique_keys:
                cache_key = f"{key[0]}:{key[1]}"  # endpoint_id:item_uuid
                cached_item = self.cache.get(cache_key)
                if cached_item:
                    key_map[key] = cached_item
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        # Batch fetch uncached items
        if uncached_keys:
            try:
                for item in ItemModel.batch_get(uncached_keys):
                    normalized = _normalize_model(item)
                    key = (item.endpoint_id, item.item_uuid)
                    key_map[key] = normalized

                    # Cache the result if enabled
                    if self.cache_enabled:
                        cache_key = f"{key[0]}:{key[1]}"
                        self.cache.set(
                            cache_key, normalized, ttl=Config.get_cache_ttl()
                        )

            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)

        return Promise.resolve([key_map.get(key) for key in keys])


class ProviderItemLoader(_SafeDataLoader):
    """Batch loader for ProviderItemModel keyed by (endpoint_id, provider_item_uuid)."""

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(ProviderItemLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "provider_item")
            )

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, Dict[str, Any]] = {}
        uncached_keys = []

        # Check cache first if enabled
        if self.cache_enabled:
            for key in unique_keys:
                cache_key = f"{key[0]}:{key[1]}"  # endpoint_id:provider_item_uuid
                cached_item = self.cache.get(cache_key)
                if cached_item:
                    key_map[key] = cached_item
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        # Batch fetch uncached items
        if uncached_keys:
            try:
                for pi in ProviderItemModel.batch_get(uncached_keys):
                    normalized = _normalize_model(pi)
                    key = (pi.endpoint_id, pi.provider_item_uuid)
                    key_map[key] = normalized

                    # Cache the result if enabled
                    if self.cache_enabled:
                        cache_key = f"{key[0]}:{key[1]}"
                        self.cache.set(
                            cache_key, normalized, ttl=Config.get_cache_ttl()
                        )

            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)

        return Promise.resolve([key_map.get(key) for key in keys])


class SegmentLoader(_SafeDataLoader):
    """Batch loader for SegmentModel keyed by (endpoint_id, segment_uuid)."""

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(SegmentLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(Config.get_cache_name("models", "segment"))

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, Dict[str, Any]] = {}
        uncached_keys = []

        # Check cache first if enabled
        if self.cache_enabled:
            for key in unique_keys:
                cache_key = f"{key[0]}:{key[1]}"  # endpoint_id:segment_uuid
                cached_item = self.cache.get(cache_key)
                if cached_item:
                    key_map[key] = cached_item
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        # Batch fetch uncached items
        if uncached_keys:
            try:
                for segment in SegmentModel.batch_get(uncached_keys):
                    normalized = _normalize_model(segment)
                    key = (segment.endpoint_id, segment.segment_uuid)
                    key_map[key] = normalized

                    # Cache the result if enabled
                    if self.cache_enabled:
                        cache_key = f"{key[0]}:{key[1]}"
                        self.cache.set(
                            cache_key, normalized, ttl=Config.get_cache_ttl()
                        )

            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)

        return Promise.resolve([key_map.get(key) for key in keys])


class RequestLoader(_SafeDataLoader):
    """Batch loader for RequestModel keyed by (endpoint_id, request_uuid)."""

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(RequestLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(Config.get_cache_name("models", "request"))

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, Dict[str, Any]] = {}
        uncached_keys = []

        # Check cache first if enabled
        if self.cache_enabled:
            for key in unique_keys:
                cache_key = f"{key[0]}:{key[1]}"  # endpoint_id:request_uuid
                cached_item = self.cache.get(cache_key)
                if cached_item:
                    key_map[key] = cached_item
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        # Batch fetch uncached items
        if uncached_keys:
            try:
                for request in RequestModel.batch_get(uncached_keys):
                    normalized = _normalize_model(request)
                    key = (request.endpoint_id, request.request_uuid)
                    key_map[key] = normalized

                    # Cache the result if enabled
                    if self.cache_enabled:
                        cache_key = f"{key[0]}:{key[1]}"
                        self.cache.set(
                            cache_key, normalized, ttl=Config.get_cache_ttl()
                        )

            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)

        return Promise.resolve([key_map.get(key) for key in keys])


class QuoteLoader(_SafeDataLoader):
    """Batch loader for QuoteModel keyed by (request_uuid, quote_uuid)."""

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(QuoteLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(Config.get_cache_name("models", "quote"))

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, Dict[str, Any]] = {}
        uncached_keys = []

        # Check cache first if enabled
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

        # Batch fetch uncached items
        if uncached_keys:
            try:
                for quote in QuoteModel.batch_get(uncached_keys):
                    normalized = _normalize_model(quote)
                    key = (quote.request_uuid, quote.quote_uuid)
                    key_map[key] = normalized

                    # Cache the result if enabled
                    if self.cache_enabled:
                        cache_key = f"{key[0]}:{key[1]}"
                        self.cache.set(
                            cache_key, normalized, ttl=Config.get_cache_ttl()
                        )

            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)

        return Promise.resolve([key_map.get(key) for key in keys])


class RequestLoaders:
    """Container for all DataLoaders scoped to a single GraphQL request."""

    def __init__(self, context: Dict[str, Any], cache_enabled: bool = True):
        logger = context.get("logger")
        self.cache_enabled = cache_enabled

        self.item_loader = ItemLoader(logger=logger, cache_enabled=cache_enabled)
        self.provider_item_loader = ProviderItemLoader(
            logger=logger, cache_enabled=cache_enabled
        )
        self.segment_loader = SegmentLoader(logger=logger, cache_enabled=cache_enabled)
        self.request_loader = RequestLoader(logger=logger, cache_enabled=cache_enabled)
        self.quote_loader = QuoteLoader(logger=logger, cache_enabled=cache_enabled)

    def invalidate_cache(self, entity_type: str, entity_keys: Dict[str, str]):
        """Invalidate specific cache entries when entities are modified."""
        if not self.cache_enabled:
            return

        if entity_type == "item" and "item_uuid" in entity_keys:
            cache_key = f"{entity_keys.get('endpoint_id')}:{entity_keys['item_uuid']}"
            if hasattr(self.item_loader, "cache"):
                self.item_loader.cache.delete(cache_key)
        elif entity_type == "provider_item" and "provider_item_uuid" in entity_keys:
            cache_key = (
                f"{entity_keys.get('endpoint_id')}:{entity_keys['provider_item_uuid']}"
            )
            if hasattr(self.provider_item_loader, "cache"):
                self.provider_item_loader.cache.delete(cache_key)
        elif entity_type == "segment" and "segment_uuid" in entity_keys:
            cache_key = (
                f"{entity_keys.get('endpoint_id')}:{entity_keys['segment_uuid']}"
            )
            if hasattr(self.segment_loader, "cache"):
                self.segment_loader.cache.delete(cache_key)
        elif entity_type == "request" and "request_uuid" in entity_keys:
            cache_key = (
                f"{entity_keys.get('endpoint_id')}:{entity_keys['request_uuid']}"
            )
            if hasattr(self.request_loader, "cache"):
                self.request_loader.cache.delete(cache_key)
        elif entity_type == "quote" and "quote_uuid" in entity_keys:
            cache_key = f"{entity_keys.get('request_uuid')}:{entity_keys['quote_uuid']}"
            if hasattr(self.quote_loader, "cache"):
                self.quote_loader.cache.delete(cache_key)


def get_loaders(context: Dict[str, Any]) -> RequestLoaders:
    """Fetch or initialize request-scoped loaders from the GraphQL context."""
    if context is None:
        context = {}

    loaders = context.get("batch_loaders")
    if not loaders:
        # Check if caching is enabled
        cache_enabled = Config.is_cache_enabled()
        loaders = RequestLoaders(context, cache_enabled=cache_enabled)
        context["batch_loaders"] = loaders
    return loaders


def clear_loaders(context: Dict[str, Any]) -> None:
    """Clear loaders from context (useful for tests)."""
    if context is None:
        return
    context.pop("batch_loaders", None)
