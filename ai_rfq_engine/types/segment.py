#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType

from ..models.batch_loaders import get_loaders


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
    contacts = List("ai_rfq_engine.types.segment_contact.SegmentContactType")

    # ------- Nested resolvers -------

    def resolve_contacts(parent, info):
        """Resolve nested SegmentContacts for this segment."""
        from ..models.segment_contact import SegmentContactModel
        from .segment_contact import SegmentContactType

        # Check if already embedded
        existing = getattr(parent, "contacts", None)
        if isinstance(existing, list) and existing:
            return [SegmentContactType(**contact) if isinstance(contact, dict) else contact for contact in existing]

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
                SegmentContactType(**contact) for contact in (contacts or [])
            ]
        )


class SegmentListType(ListObjectType):
    segment_list = List(SegmentType)
