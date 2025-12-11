#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import discount_rule
from ..types.discount_rule import DiscountRuleListType, DiscountRuleType


def resolve_discount_rule(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DiscountRuleType:
    return discount_rule.resolve_discount_rule(info, **kwargs)


def resolve_discount_rule_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> DiscountRuleListType:
    return discount_rule.resolve_discount_rule_list(info, **kwargs)
