#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import request
from ..types.request import RequestListType, RequestType


def resolve_request(info: ResolveInfo, **kwargs: Dict[str, Any]) -> RequestType | None:
    return request.resolve_request(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "request"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_request_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> RequestListType:
    return request.resolve_request_list(info, **kwargs)
