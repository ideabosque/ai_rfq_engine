#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import provider_item_batches
from ..types.provider_item_batches import (
    ProviderItemBatchListType,
    ProviderItemBatchType,
)


def resolve_provider_item_batch(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ProviderItemBatchType | None:
    return provider_item_batches.resolve_provider_item_batch(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "provider_item_batches"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_provider_item_batch_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ProviderItemBatchListType:
    return provider_item_batches.resolve_provider_item_batch_list(info, **kwargs)
