#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import quote
from ..types.quote import QuoteListType, QuoteType


def resolve_quote(info: ResolveInfo, **kwargs: Dict[str, Any]) -> QuoteType | None:
    return quote.resolve_quote(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "quote"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_quote_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> QuoteListType:
    return quote.resolve_quote_list(info, **kwargs)
