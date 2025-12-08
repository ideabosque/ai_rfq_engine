#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import discount_prompt
from ..types.discount_prompt import DiscountPromptListType, DiscountPromptType


def resolve_discount_prompt(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DiscountPromptType | None:
    return discount_prompt.resolve_discount_prompt(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "discount_prompt"),
)
def resolve_discount_prompt_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DiscountPromptListType:
    return discount_prompt.resolve_discount_prompt_list(info, **kwargs)
