#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import segment
from ..types.segment import SegmentListType, SegmentType


def resolve_segment(info: ResolveInfo, **kwargs: Dict[str, Any]) -> SegmentType | None:
    return segment.resolve_segment(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "segment"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_segment_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> SegmentListType:
    return segment.resolve_segment_list(info, **kwargs)
