#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import quote_item
from ..types.quote_item import QuoteItemListType, QuoteItemType


def resolve_quote_item(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> QuoteItemType | None:
    return quote_item.resolve_quote_item(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "quote_item"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_quote_item_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> QuoteItemListType:
    return quote_item.resolve_quote_item_list(info, **kwargs)
