#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import provider_item
from ..types.provider_item import ProviderItemListType, ProviderItemType


def resolve_provider_item(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ProviderItemType:
    return provider_item.resolve_provider_item(info, **kwargs)


def resolve_provider_item_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ProviderItemListType:
    return provider_item.resolve_provider_item_list(info, **kwargs)
