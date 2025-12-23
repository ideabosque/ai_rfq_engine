#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from silvaengine_utility.cache import HybridCacheEngine

from .base import Key, SafeDataLoader, normalize_model
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
from .request_loaders import RequestLoaders, clear_loaders, get_loaders
from .request_loader import RequestLoader
from .segment_contact_by_segment_loader import SegmentContactBySegmentLoader
from .segment_contact_loader import SegmentContactLoader
from .segment_loader import SegmentLoader
from .provider_item_batch_loader import ProviderItemBatchLoader 

# Backwards-compatible aliases for prior internal names
_normalize_model = normalize_model
_SafeDataLoader = SafeDataLoader

__all__ = [
    "Key",
    "SafeDataLoader",
    "normalize_model",
    "_SafeDataLoader",
    "_normalize_model",
    "HybridCacheEngine",
    "DiscountPromptGlobalLoader",
    "DiscountPromptBySegmentLoader",
    "DiscountPromptByItemLoader",
    "DiscountPromptByProviderItemLoader",
    "FilesByRequestLoader",
    "InstallmentListLoader",
    "ItemLoader",
    "ItemPriceTierByItemLoader",
    "ItemPriceTierByProviderItemLoader",
    "ProviderItemBatchListLoader",
    "ProviderItemLoader",
    "ProviderItemsByItemLoader",
    "QuoteItemListLoader",
    "QuoteLoader",
    "QuotesByRequestLoader",
    "RequestLoaders",
    "RequestLoader",
    "SegmentContactBySegmentLoader",
    "SegmentContactLoader",
    "SegmentLoader",
    "ProviderItemBatchLoader",
    "clear_loaders",
    "get_loaders",
]
