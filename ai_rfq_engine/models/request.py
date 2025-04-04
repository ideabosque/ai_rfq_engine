#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
import traceback
from typing import Any, Dict

import pendulum
from graphene import ResolveInfo
from pynamodb.attributes import (
    ListAttribute,
    MapAttribute,
    UnicodeAttribute,
    UTCDateTimeAttribute,
)
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

from ..types.request import RequestListType, RequestType


class ContactUuidIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "contact_uuid-index"

    endpoint_id = UnicodeAttribute(hash_key=True)
    contact_uuid = UnicodeAttribute(range_key=True)


class RequestModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-requests"

    endpoint_id = UnicodeAttribute(hash_key=True)
    request_uuid = UnicodeAttribute(range_key=True)
    contact_uuid = UnicodeAttribute()
    request_title = UnicodeAttribute()
    request_description = UnicodeAttribute(null=True)
    items = ListAttribute(of=MapAttribute, default=[])
    status = UnicodeAttribute(default="initial")
    expired_at = UTCDateTimeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    contact_uuid_index = ContactUuidIndex()


def create_request_table(logger: logging.Logger) -> bool:
    """Create the Request table if it doesn't exist."""
    if not RequestModel.exists():
        # Create with on-demand billing (PAY_PER_REQUEST)
        RequestModel.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        logger.info("The Request table has been created.")
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_request(endpoint_id: str, request_uuid: str) -> RequestModel:
    return RequestModel.get(endpoint_id, request_uuid)


def get_request_count(endpoint_id: str, request_uuid: str) -> int:
    return RequestModel.count(endpoint_id, RequestModel.request_uuid == request_uuid)


def get_request_type(info: ResolveInfo, request: RequestModel) -> RequestType:
    try:
        request = request.__dict__["attribute_values"]
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    return RequestType(**Utility.json_loads(Utility.json_dumps(request)))


def resolve_request(info: ResolveInfo, **kwargs: Dict[str, Any]) -> RequestType:
    return get_request_type(
        info,
        get_request(kwargs["endpoint_id"], kwargs["request_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["endpoint_id", "request_uuid", "contact_uuid"],
    list_type_class=RequestListType,
    type_funct=get_request_type,
)
def resolve_request_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    endpoint_id = kwargs.get("endpoint_id")
    contact_uuid = kwargs.get("contact_uuid")
    request_title = kwargs.get("request_title")
    request_description = kwargs.get("request_description")
    statuses = kwargs.get("statuses")
    from_expired_at = kwargs.get("from_expired_at")
    to_expired_at = kwargs.get("to_expired_at")

    args = []
    inquiry_funct = RequestModel.scan
    count_funct = RequestModel.count
    if endpoint_id:
        args = [endpoint_id, None]
        inquiry_funct = RequestModel.query
        if contact_uuid:
            count_funct = RequestModel.contact_uuid_index.count
            args[1] = RequestModel.contact_uuid_index == contact_uuid
            inquiry_funct = RequestModel.contact_uuid_index.query

    the_filters = None
    if request_title:
        the_filters &= RequestModel.request_title.contains(request_title)
    if request_description:
        the_filters &= RequestModel.request_description.contains(request_description)
    if statuses:
        the_filters &= RequestModel.status.is_in(*statuses)
    if from_expired_at and to_expired_at:
        the_filters &= RequestModel.expired_at.between(from_expired_at, to_expired_at)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "endpoint_id",
        "range_key": "request_uuid",
    },
    model_funct=get_request,
    count_funct=get_request_count,
    type_funct=get_request_type,
)
def insert_update_request(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    endpoint_id = kwargs.get("endpoint_id")
    request_uuid = kwargs.get("request_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "contact_uuid",
            "request_title",
            "request_description",
            "items",
            "status",
            "expired_at",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]
        RequestModel(
            endpoint_id,
            request_uuid,
            **cols,
        ).save()
        return

    request = kwargs.get("entity")
    actions = [
        RequestModel.updated_by.set(kwargs["updated_by"]),
        RequestModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to RequestModel attributes
    field_map = {
        "contact_uuid": RequestModel.contact_uuid,
        "request_title": RequestModel.request_title,
        "request_description": RequestModel.request_description,
        "items": RequestModel.items,
        "status": RequestModel.status,
        "expired_at": RequestModel.expired_at,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the request
    request.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "endpoint_id",
        "range_key": "request_uuid",
    },
    model_funct=get_request,
)
def delete_request(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
