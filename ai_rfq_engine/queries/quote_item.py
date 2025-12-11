#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import quote_item
from ..types.quote_item import QuoteItemListType, QuoteItemType


def resolve_quote_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> QuoteItemType:
    return quote_item.resolve_quote_item(info, **kwargs)


def resolve_quote_item_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> QuoteItemListType:
    return quote_item.resolve_quote_item_list(info, **kwargs)
