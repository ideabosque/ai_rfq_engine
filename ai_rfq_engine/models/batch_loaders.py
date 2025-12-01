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
from .discount_rule import DiscountRuleModel
from .file import FileModel
from .installment import InstallmentModel
from .item import ItemModel
from .item_price_tier import ItemPriceTierModel
from .provider_item import ProviderItemModel
from .provider_item_batches import ProviderItemBatchModel
from .quote import QuoteModel
from .quote_item import QuoteItemModel
from .request import RequestModel
from .segment import SegmentModel
from .segment_contact import SegmentContactModel

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
            cache_meta = Config.get_cache_entity_config().get("item")
            self.cache_func_prefix = ""
            if cache_meta:
                self.cache_func_prefix = ".".join([cache_meta.get("module"), cache_meta.get("getter")])
    def generate_cache_key(self, key: Key) -> str:
        key_data = ":".join([str(key), str({})])
        return self.cache._generate_key(
            self.cache_func_prefix,
            key_data
        )

    def _get_cache_data(self, key: Key) -> Dict[str, Any]:
        cache_key = self.generate_cache_key(key)
        cache_data = self.cache.get(cache_key)
        if cache_data is not None and not isinstance(cache_data, dict):  # pragma: no cover - defensive
            cache_data = _normalize_model(cache_data)
        return cache_data

    def _set_cache_data(self, key: Key, data: Any) -> None:
        cache_key = self.generate_cache_key(key)
        self.cache.set(cache_key, data, ttl=Config.get_cache_ttl())

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, Dict[str, Any]] = {}
        uncached_keys = []

        # Check cache first if enabled
        if self.cache_enabled:
            for key in unique_keys:
                # cache_key = f"{key[0]}:{key[1]}"  # endpoint_id:item_uuid
                # cached_item = self.cache.get(cache_key)
                cached_item = self._get_cache_data(key)
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
                    key = (item.endpoint_id, item.item_uuid)

                    # Cache the result if enabled
                    if self.cache_enabled:
                        self._set_cache_data(key, item)
                        # cache_key = f"{key[0]}:{key[1]}"
                        # self.cache.set(
                        #     cache_key, normalized, ttl=Config.get_cache_ttl()
                        # )
                    
                    normalized = _normalize_model(item)
                    key_map[key] = normalized
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
            cache_meta = Config.get_cache_entity_config().get("provider_item")
            self.cache_func_prefix = ""
            if cache_meta:
                self.cache_func_prefix = ".".join([cache_meta.get("module"), cache_meta.get("getter")])
    def generate_cache_key(self, key: Key) -> str:
        key_data = ":".join([str(key), str({})])
        return self.cache._generate_key(
            self.cache_func_prefix,
            key_data
        )

    def _get_cache_data(self, key: Key) -> Dict[str, Any]:
        cache_key = self.generate_cache_key(key)
        cache_data = self.cache.get(cache_key)
        if cache_data is not None and not isinstance(cache_data, dict):  # pragma: no cover - defensive
            cache_data = _normalize_model(cache_data)
        return cache_data

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, Dict[str, Any]] = {}
        uncached_keys = []

        # Check cache first if enabled
        if self.cache_enabled:
            for key in unique_keys:
                # cache_key = f"{key[0]}:{key[1]}"  # endpoint_id:provider_item_uuid
                # cached_item = self.cache.get(cache_key)
                cached_item = self._get_cache_data(key)
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
                    key = (pi.endpoint_id, pi.provider_item_uuid)

                    # Cache the result if enabled
                    if self.cache_enabled:
                        # cache_key = f"{key[0]}:{key[1]}"
                        # self.cache.set(
                        #     cache_key, normalized, ttl=Config.get_cache_ttl()
                        # )
                        self._set_cache_data(key, pi)

                    normalized = _normalize_model(pi)
                    key_map[key] = normalized
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)

        return Promise.resolve([key_map.get(key) for key in keys])


class ProviderItemsByItemLoader(_SafeDataLoader):
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

        # Check cache first if enabled
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
                normalized = [_normalize_model(pi) for pi in provider_items]
                key_map[(endpoint_id, item_uuid)] = normalized

                if self.cache_enabled:
                    cache_key = f"{endpoint_id}:{item_uuid}:list"
                    self.cache.set(cache_key, normalized, ttl=Config.get_cache_ttl())
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[(endpoint_id, item_uuid)] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])


class ProviderItemBatchListLoader(_SafeDataLoader):
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

        # Check cache first if enabled
        if self.cache_enabled:
            for key in unique_keys:
                cached_batches = self.cache.get(key)
                if cached_batches is not None:
                    key_map[key] = cached_batches
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        # Batch fetch uncached batches
        for provider_item_uuid in uncached_keys:
            try:
                batches = ProviderItemBatchModel.query(provider_item_uuid)
                normalized = [_normalize_model(batch) for batch in batches]
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


class QuoteItemListLoader(_SafeDataLoader):
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

        # Check cache first if enabled
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
                normalized = [_normalize_model(item) for item in items]
                key_map[quote_uuid] = normalized

                if self.cache_enabled:
                    self.cache.set(quote_uuid, normalized, ttl=Config.get_cache_ttl())
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[quote_uuid] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])


class InstallmentListLoader(_SafeDataLoader):
    """Batch loader returning installments keyed by quote_uuid."""

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(InstallmentListLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "installment")
            )

    def batch_load_fn(self, keys: List[str]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[str, List[Dict[str, Any]]] = {}
        uncached_keys: List[str] = []

        # Check cache first if enabled
        if self.cache_enabled:
            for key in unique_keys:
                cached_installments = self.cache.get(key)
                if cached_installments is not None:
                    key_map[key] = cached_installments
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        for quote_uuid in uncached_keys:
            try:
                installments = InstallmentModel.query(quote_uuid)
                normalized = [_normalize_model(inst) for inst in installments]
                key_map[quote_uuid] = normalized

                if self.cache_enabled:
                    self.cache.set(quote_uuid, normalized, ttl=Config.get_cache_ttl())
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[quote_uuid] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])


class DiscountRuleByItemLoader(_SafeDataLoader):
    """Batch loader returning discount rules keyed by item_uuid."""

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(DiscountRuleByItemLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "discount_rule")
            )

    def batch_load_fn(self, keys: List[str]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[str, List[Dict[str, Any]]] = {}
        uncached_keys: List[str] = []

        if self.cache_enabled:
            for key in unique_keys:
                cached_rules = self.cache.get(key)
                if cached_rules is not None:
                    key_map[key] = cached_rules
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        for item_uuid in uncached_keys:
            try:
                rules = DiscountRuleModel.query(item_uuid)
                normalized = [_normalize_model(rule) for rule in rules]
                key_map[item_uuid] = normalized

                if self.cache_enabled:
                    self.cache.set(item_uuid, normalized, ttl=Config.get_cache_ttl())
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[item_uuid] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])


class ItemPriceTierByProviderItemLoader(_SafeDataLoader):
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

        # Check cache first if enabled
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

        # Batch fetch uncached tiers
        for item_uuid, provider_item_uuid in uncached_keys:
            try:
                tiers = ItemPriceTierModel.provider_item_uuid_index.query(
                    item_uuid, ItemPriceTierModel.provider_item_uuid == provider_item_uuid
                )
                normalized = [_normalize_model(tier) for tier in tiers]
                key_map[(item_uuid, provider_item_uuid)] = normalized

                if self.cache_enabled:
                    cache_key = f"{item_uuid}:{provider_item_uuid}"
                    self.cache.set(cache_key, normalized, ttl=Config.get_cache_ttl())
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[(item_uuid, provider_item_uuid)] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])


class ItemPriceTierByItemLoader(_SafeDataLoader):
    """Batch loader returning price tiers keyed by item_uuid."""

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(ItemPriceTierByItemLoader, self).__init__(
            logger=logger, cache_enabled=cache_enabled, **kwargs
        )
        if self.cache_enabled:
            self.cache = HybridCacheEngine(
                Config.get_cache_name("models", "item_price_tier")
            )

    def batch_load_fn(self, keys: List[str]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[str, List[Dict[str, Any]]] = {}
        uncached_keys: List[str] = []

        if self.cache_enabled:
            for key in unique_keys:
                cached = self.cache.get(key)
                if cached is not None:
                    key_map[key] = cached
                else:
                    uncached_keys.append(key)
        else:
            uncached_keys = unique_keys

        for item_uuid in uncached_keys:
            try:
                tiers = ItemPriceTierModel.query(item_uuid)
                normalized = [_normalize_model(tier) for tier in tiers]
                key_map[item_uuid] = normalized

                if self.cache_enabled:
                    self.cache.set(item_uuid, normalized, ttl=Config.get_cache_ttl())
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[item_uuid] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])


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


class QuotesByRequestLoader(_SafeDataLoader):
    """Batch loader returning all quotes for a request keyed by request_uuid."""

    def batch_load_fn(self, keys: List[str]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[str, List[Dict[str, Any]]] = {}

        for request_uuid in unique_keys:
            try:
                quotes = QuoteModel.query(request_uuid)
                key_map[request_uuid] = [_normalize_model(q) for q in quotes]
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[request_uuid] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])


class FilesByRequestLoader(_SafeDataLoader):
    """Batch loader returning all files for a request keyed by request_uuid."""

    def batch_load_fn(self, keys: List[str]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[str, List[Dict[str, Any]]] = {}

        for request_uuid in unique_keys:
            try:
                files = FileModel.query(request_uuid)
                key_map[request_uuid] = [_normalize_model(f) for f in files]
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[request_uuid] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])


class SegmentContactBySegmentLoader(_SafeDataLoader):
    """Batch loader returning contacts for a segment keyed by (endpoint_id, segment_uuid)."""

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, List[Dict[str, Any]]] = {}

        for endpoint_id, segment_uuid in unique_keys:
            try:
                contacts = SegmentContactModel.segment_uuid_index.query(
                    endpoint_id, SegmentContactModel.segment_uuid == segment_uuid
                )
                key_map[(endpoint_id, segment_uuid)] = [
                    _normalize_model(contact) for contact in contacts
                ]
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[(endpoint_id, segment_uuid)] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])


class RequestLoaders:
    """Container for all DataLoaders scoped to a single GraphQL request."""

    def __init__(self, context: Dict[str, Any], cache_enabled: bool = True):
        logger = context.get("logger")
        self.cache_enabled = cache_enabled

        self.item_loader = ItemLoader(logger=logger, cache_enabled=cache_enabled)
        self.provider_item_loader = ProviderItemLoader(
            logger=logger, cache_enabled=cache_enabled
        )
        self.provider_items_by_item_loader = ProviderItemsByItemLoader(
            logger=logger, cache_enabled=cache_enabled
        )
        self.provider_item_batch_list_loader = ProviderItemBatchListLoader(
            logger=logger, cache_enabled=cache_enabled
        )
        self.item_price_tier_by_provider_item_loader = (
            ItemPriceTierByProviderItemLoader(
                logger=logger, cache_enabled=cache_enabled
            )
        )
        self.item_price_tier_by_item_loader = ItemPriceTierByItemLoader(
            logger=logger, cache_enabled=cache_enabled
        )
        self.quote_item_list_loader = QuoteItemListLoader(
            logger=logger, cache_enabled=cache_enabled
        )
        self.installment_list_loader = InstallmentListLoader(
            logger=logger, cache_enabled=cache_enabled
        )
        self.discount_rule_by_item_loader = DiscountRuleByItemLoader(
            logger=logger, cache_enabled=cache_enabled
        )
        self.segment_loader = SegmentLoader(logger=logger, cache_enabled=cache_enabled)
        self.request_loader = RequestLoader(logger=logger, cache_enabled=cache_enabled)
        self.quote_loader = QuoteLoader(logger=logger, cache_enabled=cache_enabled)
        self.quotes_by_request_loader = QuotesByRequestLoader(
            logger=logger, cache_enabled=cache_enabled
        )
        self.files_by_request_loader = FilesByRequestLoader(
            logger=logger, cache_enabled=cache_enabled
        )
        self.segment_contact_by_segment_loader = SegmentContactBySegmentLoader(
            logger=logger, cache_enabled=cache_enabled
        )

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
            # Also clear provider_items_by_item_loader using item_uuid list cache if provided
            if (
                hasattr(self, "provider_items_by_item_loader")
                and hasattr(self.provider_items_by_item_loader, "cache")
                and "item_uuid" in entity_keys
            ):
                list_cache_key = (
                    f"{entity_keys.get('endpoint_id')}:{entity_keys['item_uuid']}:list"
                )
                self.provider_items_by_item_loader.cache.delete(list_cache_key)
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
            if hasattr(self, "quote_item_list_loader") and hasattr(
                self.quote_item_list_loader, "cache"
            ):
                self.quote_item_list_loader.cache.delete(entity_keys["quote_uuid"])
            if hasattr(self, "installment_list_loader") and hasattr(
                self.installment_list_loader, "cache"
            ):
                self.installment_list_loader.cache.delete(entity_keys["quote_uuid"])
        elif entity_type == "provider_item_batch" and "provider_item_uuid" in entity_keys:
            cache_key = entity_keys["provider_item_uuid"]
            if hasattr(self, "provider_item_batch_list_loader") and hasattr(
                self.provider_item_batch_list_loader, "cache"
            ):
                self.provider_item_batch_list_loader.cache.delete(cache_key)
        elif (
            entity_type == "item_price_tier"
            and "item_uuid" in entity_keys
            and "provider_item_uuid" in entity_keys
        ):
            cache_key = f"{entity_keys['item_uuid']}:{entity_keys['provider_item_uuid']}"
            if hasattr(self, "item_price_tier_by_provider_item_loader") and hasattr(
                self.item_price_tier_by_provider_item_loader, "cache"
            ):
                self.item_price_tier_by_provider_item_loader.cache.delete(cache_key)
            if hasattr(self, "item_price_tier_by_item_loader") and hasattr(
                self.item_price_tier_by_item_loader, "cache"
            ):
                self.item_price_tier_by_item_loader.cache.delete(
                    entity_keys["item_uuid"]
                )
        elif entity_type == "discount_rule" and "item_uuid" in entity_keys:
            cache_key = entity_keys["item_uuid"]
            if hasattr(self, "discount_rule_by_item_loader") and hasattr(
                self.discount_rule_by_item_loader, "cache"
            ):
                self.discount_rule_by_item_loader.cache.delete(cache_key)


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
