# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Mutation, String

from ..models.segment_contact import (
    delete_segment_contact,
    insert_update_segment_contact,
)
from ..types.segment_contact import SegmentContactType


class InsertUpdateSegmentContact(Mutation):
    segment_contact = Field(SegmentContactType)

    class Arguments:
        segment_uuid = String(required=True)
        contact_uuid = String(required=True)
        consumer_corporation_uuid = String(required=False)
        email = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateSegmentContact":
        try:
            segment_contact = insert_update_segment_contact(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateSegmentContact(segment_contact=segment_contact)


class DeleteSegmentContact(Mutation):
    ok = Boolean()

    class Arguments:
        segment_uuid = String(required=True)
        contact_uuid = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "DeleteSegmentContact":
        try:
            ok = delete_segment_contact(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteSegmentContact(ok=ok)
