#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from ...handlers.config import Config
from .discount_prompt_by_scope_loaders import (
    DiscountPromptGlobalLoader,
    DiscountPromptByItemLoader,
    DiscountPromptByProviderItemLoader,
    DiscountPromptBySegmentLoader,
)
from .files_by_request_loader import FilesByRequestLoader
from .installment_list_loader import InstallmentListLoader
from .item_loader import ItemLoader
from .item_price_tier_by_item_loader import ItemPriceTierByItemLoader
from .item_price_tier_by_provider_item_loader import ItemPriceTierByProviderItemLoader
from .provider_item_batch_list_loader import ProviderItemBatchListLoader
from .provider_item_loader import ProviderItemLoader
from .provider_items_by_item_loader import ProviderItemsByItemLoader
from .quote_item_list_loader import QuoteItemListLoader
from .quote_loader import QuoteLoader
from .quotes_by_request_loader import QuotesByRequestLoader
from .request_loader import RequestLoader
from .segment_contact_by_segment_loader import SegmentContactBySegmentLoader
from .segment_contact_loader import SegmentContactLoader
from .segment_loader import SegmentLoader
from .provider_item_batch_loader import ProviderItemBatchLoader


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

        # Create the global discount prompt loader first
        self.discount_prompt_global_loader = DiscountPromptGlobalLoader(
            logger=logger, cache_enabled=cache_enabled
        )

        # Create scope-specific loaders and inject the global loader via constructor
        self.discount_prompt_by_segment_loader = DiscountPromptBySegmentLoader(
            logger=logger, cache_enabled=cache_enabled
        )

        self.discount_prompt_by_item_loader = DiscountPromptByItemLoader(
            logger=logger, cache_enabled=cache_enabled
        )

        self.discount_prompt_by_provider_item_loader = DiscountPromptByProviderItemLoader(
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
        self.segment_contact_loader = SegmentContactLoader(
            logger=logger, cache_enabled=cache_enabled
        )
        self.provider_item_batch_loader = ProviderItemBatchLoader(
            logger=logger, cache_enabled=cache_enabled
        )

    def invalidate_cache(self, entity_type: str, entity_keys: Dict[str, str]):
        """Invalidate specific cache entries when entities are modified."""
        if not self.cache_enabled:
            return

        if entity_type == "item" and "item_uuid" in entity_keys:
            cache_key = self.item_loader.generate_cache_key((entity_keys.get('partition_key'),entity_keys['item_uuid']))
            if hasattr(self.item_loader, "cache"):
                self.item_loader.cache.delete(cache_key)
        elif entity_type == "provider_item" and "provider_item_uuid" in entity_keys:
            cache_key = self.provider_item_loader.generate_cache_key((entity_keys.get('partition_key'),entity_keys['provider_item_uuid']))
            if hasattr(self.provider_item_loader, "cache"):
                self.provider_item_loader.cache.delete(cache_key)
            if (
                hasattr(self, "provider_items_by_item_loader")
                and hasattr(self.provider_items_by_item_loader, "cache")
                and "item_uuid" in entity_keys
            ):
                list_cache_key = self.provider_items_by_item_loader.generate_cache_key((entity_keys.get('partition_key'),entity_keys['item_uuid']))
                self.provider_items_by_item_loader.cache.delete(list_cache_key)
        elif entity_type == "segment" and "segment_uuid" in entity_keys:
            cache_key = self.segment_loader.generate_cache_key((entity_keys.get('partition_key'),entity_keys['segment_uuid']))
            if hasattr(self.segment_loader, "cache"):
                self.segment_loader.cache.delete(cache_key)
        elif entity_type == "request" and "request_uuid" in entity_keys:
            cache_key = self.request_loader.generate_cache_key((entity_keys.get('partition_key'),entity_keys['request_uuid']))
            if hasattr(self.request_loader, "cache"):
                self.request_loader.cache.delete(cache_key)
        elif entity_type == "quote" and "quote_uuid" in entity_keys:
            cache_key = self.quote_loader.generate_cache_key((entity_keys.get('request_uuid'),entity_keys['quote_uuid']))
            if hasattr(self.quote_loader, "cache"):
                self.quote_loader.cache.delete(cache_key)
            if hasattr(self, "quote_item_list_loader") and hasattr(
                self.quote_item_list_loader, "cache"
            ):
                cache_key = self.quote_item_list_loader.generate_cache_key((entity_keys.get('quote_uuid')))
                self.quote_item_list_loader.cache.delete(cache_key)
            if hasattr(self, "installment_list_loader") and hasattr(
                self.installment_list_loader, "cache"
            ):
                cache_key = self.installment_list_loader.generate_cache_key((entity_keys.get('quote_uuid')))
                self.installment_list_loader.cache.delete(cache_key)
        elif entity_type == "provider_item_batch" and "provider_item_uuid" in entity_keys:
            cache_key = self.provider_item_batch_list_loader.generate_cache_key((entity_keys.get('provider_item_uuid')))
            if hasattr(self, "provider_item_batch_list_loader") and hasattr(
                self.provider_item_batch_list_loader, "cache"
            ):
                self.provider_item_batch_list_loader.cache.delete(cache_key)
            
            if "batch_no" in entity_keys:
                if hasattr(self, "provider_item_batch_loader") and hasattr(
                    self.provider_item_batch_loader, "cache"
                ):
                    cache_key = self.provider_item_batch_loader.generate_cache_key((entity_keys.get('provider_item_uuid'), entity_keys['batch_no']))
                    self.provider_item_batch_loader.cache.delete(cache_key)
        elif (
            entity_type == "item_price_tier"
            and "item_uuid" in entity_keys
            and "provider_item_uuid" in entity_keys
        ):
            # Invalidate provider_item loader cache (3-part key with segment_uuid)
            # If segment_uuid is available, invalidate specific cache entry
            # Otherwise, rely on item_by_item_loader to clear all
            if "segment_uuid" in entity_keys:
                cache_key = self.item_price_tier_by_provider_item_loader.generate_cache_key(
                    (entity_keys.get('item_uuid'), entity_keys['provider_item_uuid'], entity_keys.get('segment_uuid'))
                )
                if hasattr(self, "item_price_tier_by_provider_item_loader") and hasattr(
                    self.item_price_tier_by_provider_item_loader, "cache"
                ):
                    self.item_price_tier_by_provider_item_loader.cache.delete(cache_key)

            # Always invalidate the item-level cache to clear all price tiers for this item
            # This ensures all segments/providers are cleared even if segment_uuid is unknown
            if hasattr(self, "item_price_tier_by_item_loader") and hasattr(
                self.item_price_tier_by_item_loader, "cache"
            ):
                cache_key = self.item_price_tier_by_item_loader.generate_cache_key((entity_keys.get('item_uuid')))
                self.item_price_tier_by_item_loader.cache.delete(
                    cache_key
                )


def get_loaders(context: Dict[str, Any]) -> RequestLoaders:
    """Fetch or initialize request-scoped loaders from the GraphQL context."""
    if context is None:
        context = {}

    loaders = context.get("batch_loaders")
    if not loaders:
        cache_enabled = Config.is_cache_enabled()
        loaders = RequestLoaders(context, cache_enabled=cache_enabled)
        context["batch_loaders"] = loaders
    return loaders


def clear_loaders(context: Dict[str, Any]) -> None:
    """Clear loaders from context (useful for tests)."""
    if context is None:
        return
    context.pop("batch_loaders", None)
