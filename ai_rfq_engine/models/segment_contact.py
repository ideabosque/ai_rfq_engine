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

from ..types.segment_contact import SegmentContactListType, SegmentContactType
from .utils import _get_segment


class ConsumerCorpExternalIdIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "consumer_corp_external_id-index"

    endpoint_id = UnicodeAttribute(hash_key=True)
    consumer_corp_external_id = UnicodeAttribute(range_key=True)


class SegmentUuidIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "segment_uuid-index"

    endpoint_id = UnicodeAttribute(hash_key=True)
    segment_uuid = UnicodeAttribute(range_key=True)


class UpdateAtIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "updated_at-index"

    endpoint_id = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class SegmentContactModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-segment_contacts"

    endpoint_id = UnicodeAttribute(hash_key=True)
    email = UnicodeAttribute(range_key=True)
    segment_uuid = UnicodeAttribute()
    contact_uuid = UnicodeAttribute(null=True)
    consumer_corp_external_id = UnicodeAttribute(default="XXXXXXXXXXXXXXXXXXXX")
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    segment_uuid_index = SegmentUuidIndex()
    consumer_corp_external_id_index = ConsumerCorpExternalIdIndex()
    updated_at_index = UpdateAtIndex()


def create_segment_contact_table(logger: logging.Logger) -> bool:
    """Create the Segment Contact table if it doesn't exist."""
    if not SegmentContactModel.exists():
        # Create with on-demand billing (PAY_PER_REQUEST)
        SegmentContactModel.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        logger.info("The SegmentContact table has been created.")
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_segment_contact(endpoint_id: str, email: str) -> SegmentContactModel:
    return SegmentContactModel.get(endpoint_id, email)


def get_segment_contact_count(endpoint_id: str, email: str) -> int:
    return SegmentContactModel.count(endpoint_id, SegmentContactModel.email == email)


def get_segment_contact_type(
    info: ResolveInfo, segment_contact: SegmentContactModel
) -> SegmentContactType:
    try:
        segment = _get_segment(
            info.context["endpoint_id"], segment_contact.segment_uuid
        )
        segment_contact: Dict = segment_contact.__dict__["attribute_values"]
        segment_contact["segment"] = segment
        segment_contact.pop("endpoint_id")
        segment_contact.pop("segment_uuid")
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    return SegmentContactType(**Utility.json_normalize(segment_contact))


def resolve_segment_contact(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> SegmentContactType | None:
    endpoint_id = info.context["endpoint_id"]
    segment_uuid = kwargs.get("segment_uuid")
    email = kwargs["email"]

    # Query using segment_uuid_index if segment_uuid is provided
    if segment_uuid:
        results = list(
            SegmentContactModel.segment_uuid_index.query(
                endpoint_id,
                SegmentContactModel.segment_uuid == segment_uuid,
                SegmentContactModel.email == email,
            )
        )
        if not results:
            return None
        segment_contact = results[0]
    else:
        count = get_segment_contact_count(endpoint_id, email)
        if count == 0:
            return None
        segment_contact = get_segment_contact(endpoint_id, email)

    return get_segment_contact_type(info, segment_contact)


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "segment_uuid",
        "email",
        "contact_uuid",
        "consumer_corp_external_id",
        "updated_at",
    ],
    list_type_class=SegmentContactListType,
    type_funct=get_segment_contact_type,
)
def resolve_segment_contact_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    segment_uuid = kwargs.get("segment_uuid")
    contact_uuid = kwargs.get("contact_uuid")
    consumer_corp_external_id = kwargs.get("consumer_corp_external_id")
    email = kwargs.get("email")
    endpoint_id = info.context.get("endpoint_id")

    args = []
    inquiry_funct = SegmentContactModel.scan
    count_funct = SegmentContactModel.count

    # Query by endpoint_id (hash key)
    if endpoint_id:
        args = [endpoint_id, None]
        inquiry_funct = SegmentContactModel.query
        count_funct = SegmentContactModel.count

        # Use appropriate index based on query parameters
        if consumer_corp_external_id:
            count_funct = SegmentContactModel.consumer_corp_external_id_index.count
            args[1] = (
                SegmentContactModel.consumer_corp_external_id
                == consumer_corp_external_id
            )
            inquiry_funct = SegmentContactModel.consumer_corp_external_id_index.query
        elif segment_uuid:
            count_funct = SegmentContactModel.segment_uuid_index.count
            args[1] = SegmentContactModel.segment_uuid == segment_uuid
            inquiry_funct = SegmentContactModel.segment_uuid_index.query

    the_filters = None  # We can add filters for the query
    if email:
        the_filters &= SegmentContactModel.email == email
    if contact_uuid:
        the_filters &= SegmentContactModel.contact_uuid == contact_uuid
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "endpoint_id",
        "range_key": "email",
    },
    range_key_required=True,
    model_funct=get_segment_contact,
    count_funct=get_segment_contact_count,
    type_funct=get_segment_contact_type,
)
def insert_update_segment_contact(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    endpoint_id = kwargs.get("endpoint_id") or info.context.get("endpoint_id")
    email = kwargs.get("email")
    if kwargs.get("entity") is None:
        cols = {
            "segment_uuid": kwargs.get("segment_uuid"),
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in ["consumer_corp_external_id", "contact_uuid"]:
            if key in kwargs:
                cols[key] = kwargs[key]
        SegmentContactModel(
            endpoint_id,
            email,
            **cols,
        ).save()
        return

    segment_contact = kwargs.get("entity")
    actions = [
        SegmentContactModel.updated_by.set(kwargs["updated_by"]),
        SegmentContactModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to SegmentContactModel attributes
    field_map = {
        "consumer_corp_external_id": SegmentContactModel.consumer_corp_external_id,
        "contact_uuid": SegmentContactModel.contact_uuid,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the segment contact
    segment_contact.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "endpoint_id",
        "range_key": "email",
    },
    model_funct=get_segment_contact,
)
def delete_segment_contact(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
