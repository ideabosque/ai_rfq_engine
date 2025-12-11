#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import segment_contact
from ..types.segment_contact import SegmentContactListType, SegmentContactType


def resolve_segment_contact(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> SegmentContactType:
    return segment_contact.resolve_segment_contact(info, **kwargs)


def resolve_segment_contact_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> SegmentContactListType:
    return segment_contact.resolve_segment_contact_list(info, **kwargs)
