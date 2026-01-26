#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import Boolean, DateTime, Field, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import SafeFloat as Float

from ..models.batch_loaders import get_loaders


class QuoteItemType(ObjectType):
    quote_uuid = String()
    quote_item_uuid = String()
    provider_item_uuid = String()
    item_uuid = String()
    partition_key = String()
    batch_no = String()
    request_uuid = String()
    qty = Float()
    price_per_uom = Float()
    subtotal = Float()
    subtotal_discount = Float()
    final_subtotal = Float()
    guardrail_price_per_uom = Float()
    slow_move_item = Boolean()

    # Nested resolver: strongly-typed nested relationships
    quote = Field(lambda: QuoteType)
    item = Field(lambda: ItemType)
    provider_item = Field(lambda: ProviderItemType)
    provider_item_batch = Field(lambda: ProviderItemBatchType)

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

    def resolve_guardrail_price_per_uom(parent, info):
        """Resolve nested Quote for this quote item using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "slow_move_item", None)
        if existing:
            return existing

        # Case 1: need to fetch using DataLoader
        provider_item_uuid = getattr(parent, "provider_item_uuid", None)
        batch_no = getattr(parent, "batch_no", None)
        partition_key = getattr(
            parent, "partition_key", None
        )  # info.context.get("partition_key")
        if not provider_item_uuid:
            return None

        loaders = get_loaders(info.context)
        if batch_no:
            return loaders.provider_item_batch_loader.load(
                (provider_item_uuid, batch_no)
            ).then(
                lambda provider_item_batch: (
                    provider_item_batch.get("guardrail_price_per_uom", None)
                    if provider_item_batch
                    else None
                )
            )
        else:
            return loaders.provider_item_loader.load(
                (partition_key, provider_item_uuid)
            ).then(
                lambda provider_item: (
                    provider_item.get("base_price_per_uom", None)
                    if provider_item
                    else None
                )
            )

    def resolve_slow_move_item(parent, info):
        """Resolve nested Quote for this quote item using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "slow_move_item", None)
        if existing:
            return existing

        # Case 1: need to fetch using DataLoader
        provider_item_uuid = getattr(parent, "provider_item_uuid", None)
        batch_no = getattr(parent, "batch_no", None)
        if not provider_item_uuid or not batch_no:
            return None

        loaders = get_loaders(info.context)
        return loaders.provider_item_batch_loader.load(
            (provider_item_uuid, batch_no)
        ).then(
            lambda provider_item_batch: (
                provider_item_batch.get("slow_move_item", None)
                if provider_item_batch
                else None
            )
        )

    # ------- Nested resolvers -------
    def resolve_quote(parent, info):
        """Resolve nested Quote for this quote item using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "quote", None)
        if isinstance(existing, dict):
            return QuoteType(**existing)
        if isinstance(existing, QuoteType):
            return existing

        # Case 1: need to fetch using DataLoader
        request_uuid = getattr(parent, "request_uuid", None)
        quote_uuid = getattr(parent, "quote_uuid", None)
        if not request_uuid or not quote_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.quote_loader.load((request_uuid, quote_uuid)).then(
            lambda quote_dict: QuoteType(**quote_dict) if quote_dict else None
        )

    def resolve_item(parent, info):
        """Resolve nested Item for this quote item using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "item", None)
        if isinstance(existing, dict):
            return ItemType(**existing)
        if isinstance(existing, ItemType):
            return existing

        # Case 1: need to fetch using DataLoader
        partition_key = info.context.get("partition_key")
        item_uuid = getattr(parent, "item_uuid", None)
        if not partition_key or not item_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.item_loader.load((partition_key, item_uuid)).then(
            lambda item_dict: ItemType(**item_dict) if item_dict else None
        )

    def resolve_provider_item(parent, info):
        """Resolve nested ProviderItem for this quote item using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "provider_item", None)
        if isinstance(existing, dict):
            return ProviderItemType(**existing)
        if isinstance(existing, ProviderItemType):
            return existing

        # Case 1: need to fetch using DataLoader
        partition_key = info.context.get("partition_key")
        provider_item_uuid = getattr(parent, "provider_item_uuid", None)
        if not partition_key or not provider_item_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.provider_item_loader.load(
            (partition_key, provider_item_uuid)
        ).then(lambda pi_dict: ProviderItemType(**pi_dict) if pi_dict else None)

    def resolve_provider_item_batch(parent, info):
        """Resolve nested ProviderItemBatch for this quote item using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "provider_item_batch", None)
        if isinstance(existing, dict):
            return ProviderItemBatchType(**existing)
        if isinstance(existing, ProviderItemBatchType):
            return existing

        # Case 1: need to fetch - look it up from the batch list
        provider_item_uuid = getattr(parent, "provider_item_uuid", None)
        batch_no = getattr(parent, "batch_no", None)
        if not provider_item_uuid or not batch_no:
            return None

        loaders = get_loaders(info.context)
        # Use provider_item_batch_list_loader to get all batches, then filter for batch_no
        return loaders.provider_item_batch_list_loader.load(provider_item_uuid).then(
            lambda batches: next(
                (
                    ProviderItemBatchType(**b)
                    for b in (batches or [])
                    if b.get("batch_no") == batch_no
                ),
                None,
            )
        )


class QuoteItemListType(ListObjectType):
    quote_item_list = List(QuoteItemType)


# Bottom imports - imported after class definitions to avoid circular imports
from .item import ItemType
from .provider_item import ProviderItemType
from .provider_item_batches import ProviderItemBatchType
from .quote import QuoteType
