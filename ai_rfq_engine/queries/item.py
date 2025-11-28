#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from silvaengine_utility import method_cache

from ..handlers.config import Config

from ..models import item
from ..types.item import ItemListType, ItemType


def resolve_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> ItemType:
    return item.resolve_item(info, **kwargs)


@method_cache(ttl=Config.get_cache_ttl(), cache_name=Config.get_cache_name('queries', 'item'))
def resolve_item_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> ItemListType:
    return item.resolve_item_list(info, **kwargs)
