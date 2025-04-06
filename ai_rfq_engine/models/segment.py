#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
import traceback
from typing import Any, Dict

import pendulum
from graphene import ResolveInfo
from pynamodb.attributes import UnicodeAttribute, UTCDateTimeAttribute
from pynamodb.indexes import AllProjection, LocalSecondaryIndex
from tenacity import retry, stop_after_attempt, wait_exponential

from silvaengine_dynamodb_base import (
    BaseModel,
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator,
)
from silvaengine_utility import Utility

from ..types.segment import SegmentListType, SegmentType


class ProviderCorpExternalIdIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "provider_corp_external_id-index"

    endpoint_id = UnicodeAttribute(hash_key=True)
    provider_corp_external_id = UnicodeAttribute(range_key=True)


class SegmentModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-segments"

    endpoint_id = UnicodeAttribute(hash_key=True)
    segment_uuid = UnicodeAttribute(range_key=True)
    provider_corp_external_id = UnicodeAttribute(default="XXXXXXXXXXXXXXXXXXX")
    segment_name = UnicodeAttribute()
    segment_description = UnicodeAttribute(null=True)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    provider_corp_external_id_index = ProviderCorpExternalIdIndex()


def create_segment_table(logger: logging.Logger) -> bool:
    """Create the Segment table if it doesn't exist."""
    if not SegmentModel.exists():
        # Create with on-demand billing (PAY_PER_REQUEST)
        SegmentModel.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        logger.info("The Segment table has been created.")
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_segment(endpoint_id: str, segment_uuid: str) -> SegmentModel:
    return SegmentModel.get(endpoint_id, segment_uuid)


def get_segment_count(endpoint_id: str, segment_uuid: str) -> int:
    return SegmentModel.count(endpoint_id, SegmentModel.segment_uuid == segment_uuid)


def get_segment_type(info: ResolveInfo, segment: SegmentModel) -> SegmentType:
    try:
        segment = segment.__dict__["attribute_values"]
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    return SegmentType(**Utility.json_loads(Utility.json_dumps(segment)))


def resolve_segment(info: ResolveInfo, **kwargs: Dict[str, Any]) -> SegmentType:
    return get_segment_type(
        info,
        get_segment(info.context["endpoint_id"], kwargs["segment_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "endpoint_id",
        "segment_uuid",
        "provider_corp_external_id",
    ],
    list_type_class=SegmentListType,
    type_funct=get_segment_type,
)
def resolve_segment_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    endpoint_id = info.context["endpoint_id"]
    provider_corp_external_id = kwargs.get("provider_corp_external_id")
    segment_name = kwargs.get("segment_name")
    segment_description = kwargs.get("segment_description")

    args = []
    inquiry_funct = SegmentModel.scan
    count_funct = SegmentModel.count
    if endpoint_id:
        args = [endpoint_id, None]
        inquiry_funct = SegmentModel.query
        if provider_corp_external_id:
            count_funct = SegmentModel.provider_corp_external_id_index.count
            args[1] = (
                SegmentModel.provider_corp_external_id == provider_corp_external_id
            )
            inquiry_funct = SegmentModel.provider_corp_external_id_index.query

    the_filters = None  # We can add filters for the query
    if segment_name:
        the_filters &= SegmentModel.segment_name.contains(segment_name)
    if segment_description:
        the_filters &= SegmentModel.segment_description.contains(segment_description)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "endpoint_id",
        "range_key": "segment_uuid",
    },
    model_funct=get_segment,
    count_funct=get_segment_count,
    type_funct=get_segment_type,
)
def insert_update_segment(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    endpoint_id = kwargs.get("endpoint_id")
    segment_uuid = kwargs.get("segment_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "provider_corp_external_id",
            "segment_name",
            "segment_description",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]
        SegmentModel(
            endpoint_id,
            segment_uuid,
            **cols,
        ).save()
        return

    segment = kwargs.get("entity")
    actions = [
        SegmentModel.updated_by.set(kwargs["updated_by"]),
        SegmentModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to SegmentModel attributes
    field_map = {
        "provider_corp_external_id": SegmentModel.provider_corp_external_id,
        "segment_name": SegmentModel.segment_name,
        "segment_description": SegmentModel.segment_description,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the segment
    segment.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "endpoint_id",
        "range_key": "segment_uuid",
    },
    model_funct=get_segment,
)
def delete_segment(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
