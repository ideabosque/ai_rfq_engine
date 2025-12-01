#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import functools
import logging
import traceback
from typing import Any, Dict

import pendulum
from graphene import ResolveInfo
from pynamodb.attributes import UnicodeAttribute, UTCDateTimeAttribute
from pynamodb.indexes import AllProjection, LocalSecondaryIndex
from silvaengine_dynamodb_base import (
    BaseModel,
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator,
)
from silvaengine_utility import Utility, method_cache
from tenacity import retry, stop_after_attempt, wait_exponential

from ..handlers.config import Config
from ..types.file import FileListType, FileType


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


def purge_cache():
    def actual_decorator(original_function):
        @functools.wraps(original_function)
        def wrapper_function(*args, **kwargs):
            try:
                # Use cascading cache purging for files
                from ..models.cache import purge_entity_cascading_cache

                context_keys = None
                entity_keys = {}
                if kwargs.get("request_uuid"):
                    entity_keys["request_uuid"] = kwargs.get("request_uuid")
                if kwargs.get("file_uuid"):
                    entity_keys["file_uuid"] = kwargs.get("file_uuid")

                result = purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="file",
                    context_keys=context_keys,
                    entity_keys=entity_keys if entity_keys else None,
                    cascade_depth=3,
                )

                ## Original function.
                result = original_function(*args, **kwargs)

                return result
            except Exception as e:
                log = traceback.format_exc()
                args[0].context.get("logger").error(log)
                raise e

        return wrapper_function

    return actual_decorator


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
@method_cache(
    ttl=Config.get_cache_ttl(), cache_name=Config.get_cache_name("models", "file")
)
def get_file(request_uuid: str, file_name: str) -> FileModel:
    return FileModel.get(request_uuid, file_name)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_file(request_uuid: str, file_name: str) -> FileModel:
    return FileModel.get(request_uuid, file_name)


def get_file_count(request_uuid: str, file_name: str) -> int:
    return FileModel.count(request_uuid, FileModel.file_name == file_name)


def get_file_type(info: ResolveInfo, file: FileModel) -> FileType:
    """
    Nested resolver approach: return minimal file data.
    - Do NOT embed 'request'.
    'request' is resolved lazily by FileType.resolve_request.
    """
    try:
        file_dict = file.__dict__["attribute_values"]
    except Exception:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise

    return FileType(**Utility.json_normalize(file_dict))


def resolve_file(info: ResolveInfo, **kwargs: Dict[str, Any]) -> FileType | None:
    count = get_file_count(kwargs["request_uuid"], kwargs["file_name"])
    if count == 0:
        return None

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


@purge_cache()
@insert_update_decorator(
    keys={
        "hash_key": "request_uuid",
        "range_key": "file_name",
    },
    range_key_required=True,
    model_funct=_get_file,
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


@purge_cache()
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
