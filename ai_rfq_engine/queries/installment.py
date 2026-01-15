#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import installment
from ..types.installment import InstallmentListType, InstallmentType


def resolve_installment(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> InstallmentType | None:
    return installment.resolve_installment(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "installment"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_installment_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> InstallmentListType:
    return installment.resolve_installment_list(info, **kwargs)
