# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Mutation, String

from ..models.segment import delete_segment, insert_update_segment
from ..types.segment import SegmentType


class InsertUpdateSegment(Mutation):
    segment = Field(SegmentType)

    class Arguments:
        segment_uuid = String(required=False)
        provider_corp_external_Id = String(required=False)
        segment_name = String(required=False)
        segment_description = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateSegment":
        try:
            segment = insert_update_segment(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateSegment(segment=segment)


class DeleteSegment(Mutation):
    ok = Boolean()

    class Arguments:
        segment_uuid = String(required=False)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteSegment":
        try:
            ok = delete_segment(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteSegment(ok=ok)
