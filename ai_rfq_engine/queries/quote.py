#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import quote
from ..types.quote import QuoteListType, QuoteType


def resolve_quote(info: ResolveInfo, **kwargs: Dict[str, Any]) -> QuoteType:
    return quote.resolve_quote(info, **kwargs)


def resolve_quote_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> QuoteListType:
    return quote.resolve_quote_list(info, **kwargs)
