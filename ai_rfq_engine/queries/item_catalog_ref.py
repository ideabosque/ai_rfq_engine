# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import item_catalog_ref
from ..types.item_catalog_ref import (
    ItemCatalogRefListType,
    ItemCatalogRefType,
)


def resolve_item_catalog_ref(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ItemCatalogRefType | None:
    return item_catalog_ref.resolve_item_catalog_ref(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "item_catalog_ref"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_item_catalog_ref_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ItemCatalogRefListType:
    return item_catalog_ref.resolve_item_catalog_ref_list(info, **kwargs)


def find_item_catalog_refs(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> List[ItemCatalogRefType]:
    return item_catalog_ref.find_item_catalog_refs(info, **kwargs)
