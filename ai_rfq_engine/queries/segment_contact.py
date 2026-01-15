#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import segment_contact
from ..types.segment_contact import SegmentContactListType, SegmentContactType


def resolve_segment_contact(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> SegmentContactType | None:
    return segment_contact.resolve_segment_contact(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "segment_contact"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_segment_contact_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> SegmentContactListType:
    return segment_contact.resolve_segment_contact_list(info, **kwargs)
