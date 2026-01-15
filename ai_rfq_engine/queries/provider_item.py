#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import provider_item
from ..types.provider_item import ProviderItemListType, ProviderItemType


def resolve_provider_item(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ProviderItemType | None:
    return provider_item.resolve_provider_item(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "provider_item"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_provider_item_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ProviderItemListType:
    return provider_item.resolve_provider_item_list(info, **kwargs)
