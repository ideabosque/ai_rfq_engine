#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import item_price_tier
from ..types.item_price_tier import ItemPriceTierListType, ItemPriceTierType


def resolve_item_price_tier(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ItemPriceTierType:
    return item_price_tier.resolve_item_price_tier(info, **kwargs)


def resolve_item_price_tier_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ItemPriceTierListType:
    return item_price_tier.resolve_item_price_tier_list(info, **kwargs)
