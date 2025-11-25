#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List, Optional, Tuple

from promise import Promise
from promise.dataloader import DataLoader

from silvaengine_utility import Utility

from .item import ItemModel
from .provider_item import ProviderItemModel
from .segment import SegmentModel
from .request import RequestModel
from .quote import QuoteModel

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

    def __init__(self, logger=None, **kwargs):
        super(_SafeDataLoader, self).__init__(**kwargs)
        self.logger = logger

    def dispatch(self):
        try:
            return super(_SafeDataLoader, self).dispatch()
        except Exception as exc:  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception(exc)
            raise

class ItemLoader(_SafeDataLoader):
    """Batch loader for ItemModel records keyed by (endpoint_id, item_uuid)."""

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, Dict[str, Any]] = {}

        try:
            for item in ItemModel.batch_get(unique_keys):
                key_map[(item.endpoint_id, item.item_uuid)] = _normalize_model(item)
        except Exception as exc:  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception(exc)

        return Promise.resolve([key_map.get(key) for key in keys])

class ProviderItemLoader(_SafeDataLoader):
    """Batch loader for ProviderItemModel keyed by (endpoint_id, provider_item_uuid)."""

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, Dict[str, Any]] = {}

        try:
            for pi in ProviderItemModel.batch_get(unique_keys):
                key_map[(pi.endpoint_id, pi.provider_item_uuid)] = _normalize_model(pi)
        except Exception as exc:  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception(exc)

        return Promise.resolve([key_map.get(key) for key in keys])

class SegmentLoader(_SafeDataLoader):
    """Batch loader for SegmentModel keyed by (endpoint_id, segment_uuid)."""

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, Dict[str, Any]] = {}

        try:
            for segment in SegmentModel.batch_get(unique_keys):
                key_map[(segment.endpoint_id, segment.segment_uuid)] = _normalize_model(segment)
        except Exception as exc:  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception(exc)

        return Promise.resolve([key_map.get(key) for key in keys])

class RequestLoader(_SafeDataLoader):
    """Batch loader for RequestModel keyed by (endpoint_id, request_uuid)."""

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, Dict[str, Any]] = {}

        try:
            for request in RequestModel.batch_get(unique_keys):
                key_map[(request.endpoint_id, request.request_uuid)] = _normalize_model(request)
        except Exception as exc:  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception(exc)

        return Promise.resolve([key_map.get(key) for key in keys])

class QuoteLoader(_SafeDataLoader):
    """Batch loader for QuoteModel keyed by (request_uuid, quote_uuid)."""

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, Dict[str, Any]] = {}

        try:
            for quote in QuoteModel.batch_get(unique_keys):
                key_map[(quote.request_uuid, quote.quote_uuid)] = _normalize_model(quote)
        except Exception as exc:  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception(exc)

        return Promise.resolve([key_map.get(key) for key in keys])

class RequestLoaders:
    """Container for all DataLoaders scoped to a single GraphQL request."""

    def __init__(self, context: Dict[str, Any]):
        logger = context.get("logger")
        self.item_loader = ItemLoader(logger=logger)
        self.provider_item_loader = ProviderItemLoader(logger=logger)
        self.segment_loader = SegmentLoader(logger=logger)
        self.request_loader = RequestLoader(logger=logger)
        self.quote_loader = QuoteLoader(logger=logger)

def get_loaders(context: Dict[str, Any]) -> RequestLoaders:
    """Fetch or initialize request-scoped loaders from the GraphQL context."""
    if context is None:
        context = {}

    loaders = context.get("batch_loaders")
    if not loaders:
        loaders = RequestLoaders(context)
        context["batch_loaders"] = loaders
    return loaders

def clear_loaders(context: Dict[str, Any]) -> None:
    """Clear loaders from context (useful for tests)."""
    if context is None:
        return
    context.pop("batch_loaders", None)
