# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import bundle
from ..types.bundle import BundleListType, BundleType


def resolve_bundle(info: ResolveInfo, **kwargs: Dict[str, Any]) -> BundleType | None:
    return bundle.resolve_bundle(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "bundle"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_bundle_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> BundleListType:
    return bundle.resolve_bundle_list(info, **kwargs)
