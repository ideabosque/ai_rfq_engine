#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Field, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType

from ..models.batch_loaders import get_loaders


class SegmentContactType(ObjectType):
    partition_key = String()
    email = String()
    contact_uuid = String()
    consumer_corp_external_id = String()

    # Nested resolver: strongly-typed nested relationship
    segment_uuid = String()  # keep raw id
    segment = Field(lambda: SegmentType)

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

    # ------- Nested resolvers -------

    def resolve_segment(parent, info):
        """Resolve nested Segment for this segment_contact using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "segment", None)
        if isinstance(existing, dict):
            return SegmentType(**existing)
        if isinstance(existing, SegmentType):
            return existing

        # Case 1: need to fetch using DataLoader
        partition_key = getattr(parent, "partition_key", None)
        segment_uuid = getattr(parent, "segment_uuid", None)
        if not partition_key or not segment_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.segment_loader.load((partition_key, segment_uuid)).then(
            lambda segment_dict: SegmentType(**segment_dict) if segment_dict else None
        )


class SegmentContactListType(ListObjectType):
    segment_contact_list = List(SegmentContactType)


# Bottom imports - imported after class definitions to avoid circular imports
from .segment import SegmentType
