#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import segment
from ..types.segment import SegmentListType, SegmentType


def resolve_segment(info: ResolveInfo, **kwargs: Dict[str, Any]) -> SegmentType:
    return segment.resolve_segment(info, **kwargs)


def resolve_segment_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> SegmentListType:
    return segment.resolve_segment_list(info, **kwargs)
