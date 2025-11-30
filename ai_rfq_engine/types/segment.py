#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import JSON, Utility

from ..models.batch_loaders import get_loaders

# Use the shared normalization helper instead of a local copy.
from ..utils.normalization import normalize_to_json


class SegmentType(ObjectType):
    endpoint_id = String()
    segment_uuid = String()
    provider_corp_external_id = String()
    segment_name = String()
    segment_description = String()
    created_at = DateTime()
    updated_by = String()
    updated_at = DateTime()

    # Nested resolvers: strongly-typed nested relationships
    contacts = List(JSON)

    # ------- Nested resolvers -------

    def resolve_contacts(parent, info):
        """Resolve nested SegmentContacts for this segment."""
        # Check if already embedded
        existing = getattr(parent, "contacts", None)
        if isinstance(existing, list) and existing:
            return [normalize_to_json(contact) for contact in existing]

        # Fetch contacts for this segment
        endpoint_id = getattr(parent, "endpoint_id", None)
        segment_uuid = getattr(parent, "segment_uuid", None)
        if not endpoint_id or not segment_uuid:
            return []

        loaders = get_loaders(info.context)
        return loaders.segment_contact_by_segment_loader.load(
            (endpoint_id, segment_uuid)
        ).then(
            lambda contacts: [
                normalize_to_json(contact) for contact in (contacts or [])
            ]
        )


class SegmentListType(ListObjectType):
    segment_list = List(SegmentType)
