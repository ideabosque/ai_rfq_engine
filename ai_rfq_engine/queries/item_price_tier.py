#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import item_price_tier
from ..models.batch_loaders import get_loaders
from ..types.item_price_tier import ItemPriceTierListType, ItemPriceTierType


def resolve_item_price_tier(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ItemPriceTierType | None:
    return item_price_tier.resolve_item_price_tier(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "item_price_tier"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_item_price_tier_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ItemPriceTierListType:
    return item_price_tier.resolve_item_price_tier_list(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "item_price_tier"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_item_price_tiers(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> List[ItemPriceTierType]:
    """
    Resolve item price tiers for quote items using batch loaders.

    Uses the _combine_all_item_price_tiers utility from models.utils
    to handle the complex Promise chaining and hierarchical loading logic,
    then converts the results to ItemPriceTierType.

    Args:
        info: GraphQL resolve info
        kwargs: Must contain 'email' and optionally 'quote_items'

    Returns:
        Promise that resolves to list of ItemPriceTierType objects with price tier information
    """
    from ..models.item_price_tier import get_item_price_tier_type
    from ..models.utils import _combine_all_item_price_tiers

    loaders = get_loaders(info.context)
    partition_key = info.context.get("partition_key")
    email = kwargs.get("email")
    quote_items = kwargs.get("quote_items", [])

    # Get tier models from utility function, then convert to types
    def convert_to_types(tier_models):
        """Convert ItemPriceTierModel instances to ItemPriceTierType."""
        return [
            get_item_price_tier_type(info, tier_model) for tier_model in tier_models
        ]

    return _combine_all_item_price_tiers(
        partition_key, email, quote_items, loaders
    ).then(convert_to_types)
