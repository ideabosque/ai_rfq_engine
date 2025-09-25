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

from ..types.file import FileListType, FileType
from .utils import _get_request


class EmailIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "email-index"

    request_uuid = UnicodeAttribute(hash_key=True)
    email = UnicodeAttribute(range_key=True)


class UpdateAtIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "updated_at-index"

    request_uuid = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class FileModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-files"

    request_uuid = UnicodeAttribute(hash_key=True)
    file_name = UnicodeAttribute(range_key=True)
    email = UnicodeAttribute()
    endpoint_id = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    email_index = EmailIndex()
    updated_at_index = UpdateAtIndex()


def create_file_table(logger: logging.Logger) -> bool:
    """Create the File table if it doesn't exist."""
    if not FileModel.exists():
        # Create with on-demand billing (PAY_PER_REQUEST)
        FileModel.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        logger.info("The File table has been created.")
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_file(request_uuid: str, file_name: str) -> FileModel:
    return FileModel.get(request_uuid, file_name)


def get_file_count(request_uuid: str, file_name: str) -> int:
    return FileModel.count(request_uuid, FileModel.file_name == file_name)


def get_file_type(info: ResolveInfo, file: FileModel) -> FileType:
    try:
        request = _get_request(info.context["endpoint_id"], file.request_uuid)
        file = file.__dict__["attribute_values"]
        file["request"] = request
        file.pop("endpoint_id")
        file.pop("request_uuid")
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    return FileType(**Utility.json_normalize(file))


def resolve_file(info: ResolveInfo, **kwargs: Dict[str, Any]) -> FileType:
    return get_file_type(
        info,
        get_file(kwargs["request_uuid"], kwargs["file_name"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["request_uuid", "file_name", "email", "updated_at"],
    list_type_class=FileListType,
    type_funct=get_file_type,
)
def resolve_file_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    request_uuid = kwargs.get("request_uuid")
    email = kwargs.get("email")
    endpoint_id = info.context.get("endpoint_id")

    args = []
    inquiry_funct = FileModel.scan
    count_funct = FileModel.count
    if request_uuid:
        args = [request_uuid, None]
        inquiry_funct = FileModel.updated_at_index.query
        count_funct = FileModel.updated_at_index.count
        if email:
            inquiry_funct = FileModel.email_index.query
            args[1] = FileModel.email == email
            count_funct = FileModel.email_index.count

    the_filters = None
    if email and not request_uuid:
        the_filters &= FileModel.email == email
    if endpoint_id:
        the_filters &= FileModel.endpoint_id == endpoint_id
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "request_uuid",
        "range_key": "file_name",
    },
    range_key_required=True,
    model_funct=get_file,
    count_funct=get_file_count,
    type_funct=get_file_type,
)
def insert_update_file(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    request_uuid = kwargs.get("request_uuid")
    file_name = kwargs.get("file_name")
    if kwargs.get("entity") is None:
        cols = {
            "endpoint_id": info.context.get("endpoint_id"),
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        if "email" in kwargs:
            cols["email"] = kwargs["email"]

        FileModel(
            request_uuid,
            file_name,
            **cols,
        ).save()
        return

    file = kwargs.get("entity")
    actions = [
        FileModel.updated_by.set(kwargs["updated_by"]),
        FileModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to FileModel attributes
    field_map = {
        "email": FileModel.email,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the file
    file.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "request_uuid",
        "range_key": "file_name",
    },
    model_funct=get_file,
)
def delete_file(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
