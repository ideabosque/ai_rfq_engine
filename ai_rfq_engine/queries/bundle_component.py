# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import bundle_component
from ..types.bundle_component import BundleComponentListType, BundleComponentType


def resolve_bundle_component(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> BundleComponentType | None:
    return bundle_component.resolve_bundle_component(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "bundle_component"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_bundle_component_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> BundleComponentListType:
    return bundle_component.resolve_bundle_component_list(info, **kwargs)
