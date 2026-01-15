#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List

from graphene import ResolveInfo

from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import discount_prompt
from ..models.batch_loaders import get_loaders
from ..types.discount_prompt import DiscountPromptListType, DiscountPromptType


def resolve_discount_prompt(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DiscountPromptType | None:
    return discount_prompt.resolve_discount_prompt(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "discount_prompt"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_discount_prompt_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DiscountPromptListType:
    return discount_prompt.resolve_discount_prompt_list(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "discount_prompt"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_discount_prompts(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> List[DiscountPromptType]:
    from ..models.utils import _combine_all_discount_prompts

    loaders = get_loaders(info.context)
    partition_key = info.context.get("partition_key")
    email = kwargs["email"]
    quote_items = kwargs.get("quote_items", [])

    return _combine_all_discount_prompts(partition_key, email, quote_items, loaders)
