#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import functools
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
from silvaengine_dynamodb_base import (
    BaseModel,
    delete_decorator,
    insert_update_decorator,
    monitor_decorator,
    resolve_list_decorator,
)
from silvaengine_utility import method_cache
from tenacity import retry, stop_after_attempt, wait_exponential

from ..handlers.config import Config
from ..types.request import RequestListType, RequestType
from ..utils.normalization import normalize_to_json
from .file import resolve_file_list
from .quote import resolve_quote_list
from .utils import (
    validate_batch_exists,
    validate_item_exists,
    validate_provider_item_exists,
)


class EmailIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "email-index"

    partition_key = UnicodeAttribute(hash_key=True)
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

    partition_key = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class RequestModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-requests"

    partition_key = UnicodeAttribute(hash_key=True)
    request_uuid = UnicodeAttribute(range_key=True)
    email = UnicodeAttribute()
    endpoint_id = UnicodeAttribute()
    part_id = UnicodeAttribute()
    request_title = UnicodeAttribute()
    request_description = UnicodeAttribute(null=True)
    billing_address = MapAttribute(null=True)
    shipping_address = MapAttribute(null=True)
    items = ListAttribute(of=MapAttribute)
    notes = UnicodeAttribute(null=True)
    status = UnicodeAttribute(default="initial")
    expired_at = UTCDateTimeAttribute(null=True)
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
                # Execute original function first
                result = original_function(*args, **kwargs)

                # Then purge cache after successful operation
                from ..models.cache import purge_entity_cascading_cache

                # Get entity keys from entity parameter (for updates)
                entity_keys = {}
                entity = kwargs.get("entity")
                if entity:
                    entity_keys["request_uuid"] = getattr(entity, "request_uuid", None)

                # Fallback to kwargs (for creates/deletes)
                if not entity_keys.get("request_uuid"):
                    entity_keys["request_uuid"] = kwargs.get("request_uuid")

                # Get partition_key from context or kwargs
                partition_key = args[0].context.get("partition_key") or kwargs.get(
                    "partition_key"
                )

                purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="request",
                    context_keys=(
                        {"partition_key": partition_key} if partition_key else None
                    ),
                    entity_keys=entity_keys if entity_keys else None,
                    cascade_depth=3,
                )

                return result
            except Exception as e:
                log = traceback.format_exc()
                args[0].context.get("logger").error(log)
                raise e

        return wrapper_function

    return actual_decorator


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "request"),
    cache_enabled=Config.is_cache_enabled,
)
def get_request(partition_key: str, request_uuid: str) -> RequestModel:
    return RequestModel.get(partition_key, request_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_request(partition_key: str, request_uuid: str) -> RequestModel:
    return RequestModel.get(partition_key, request_uuid)


def get_request_count(partition_key: str, request_uuid: str) -> int:
    return RequestModel.count(partition_key, RequestModel.request_uuid == request_uuid)


def get_request_type(info: ResolveInfo, request: RequestModel) -> RequestType:
    """
    Nested resolver approach: return minimal request data.
    Those are resolved lazily by RequestType resolvers.
    """
    _ = info  # Keep for signature compatibility with decorators
    request_dict = request.__dict__["attribute_values"].copy()
    # Keep all fields including FKs - nested resolvers will handle lazy loading
    return RequestType(**normalize_to_json(request_dict))


def resolve_request(info: ResolveInfo, **kwargs: Dict[str, Any]) -> RequestType | None:
    partition_key = info.context.get("partition_key")
    count = get_request_count(partition_key, kwargs["request_uuid"])
    if count == 0:
        return None

    return get_request_type(
        info,
        get_request(partition_key, kwargs["request_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["partition_key", "request_uuid", "email", "updated_at"],
    list_type_class=RequestListType,
    type_funct=get_request_type,
)
def resolve_request_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    partition_key = info.context.get("partition_key")
    email = kwargs.get("email")
    request_title = kwargs.get("request_title")
    request_description = kwargs.get("request_description")
    statuses = kwargs.get("statuses")
    from_expired_at = kwargs.get("from_expired_at")
    to_expired_at = kwargs.get("to_expired_at")
    updated_at_gt = kwargs.get("updated_at_gt")
    updated_at_lt = kwargs.get("updated_at_lt")

    args = []
    inquiry_funct = RequestModel.scan
    count_funct = RequestModel.count
    range_key_condition = None
    if partition_key:

        # Build range key condition for updated_at when using updated_at_index
        if updated_at_gt is not None and updated_at_lt is not None:
            range_key_condition = RequestModel.updated_at.between(
                updated_at_gt, updated_at_lt
            )
        elif updated_at_gt is not None:
            range_key_condition = RequestModel.updated_at > updated_at_gt
        elif updated_at_lt is not None:
            range_key_condition = RequestModel.updated_at < updated_at_lt

        args = [partition_key, range_key_condition]
        inquiry_funct = RequestModel.updated_at_index.query
        count_funct = RequestModel.updated_at_index.count
        if email and args[1] is None:
            count_funct = RequestModel.email_index.count
            args[1] = RequestModel.email == email
            inquiry_funct = RequestModel.email_index.query

    the_filters = None
    if email and args[1] is not None and args[1] != (RequestModel.email == email):
        the_filters &= RequestModel.email == email
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


def _validate_request_items(partition_key: str, items: list) -> None:
    """Validate item_uuid, provider_item_uuid, and batch_no in request items."""
    if not items:
        return

    for idx, item in enumerate(items):
        # Validate item_uuid if provided
        if "item_uuid" in item and item["item_uuid"]:
            if not validate_item_exists(partition_key, item["item_uuid"]):
                raise ValueError(
                    f"Item at index {idx}: item_uuid '{item['item_uuid']}' does not exist"
                )

        # Validate provider_items if provided (new format)
        if "provider_items" in item and item["provider_items"]:
            for provider_idx, provider_item in enumerate(item["provider_items"]):
                # Validate provider_item_uuid in provider_items
                if (
                    "provider_item_uuid" in provider_item
                    and provider_item["provider_item_uuid"]
                ):
                    if not validate_provider_item_exists(
                        partition_key, provider_item["provider_item_uuid"]
                    ):
                        raise ValueError(
                            f"Item at index {idx}, provider_item at index {provider_idx}: "
                            f"provider_item_uuid '{provider_item['provider_item_uuid']}' does not exist"
                        )

                    # Validate batch_no if provided
                    if "batch_no" in provider_item and provider_item["batch_no"]:
                        if not validate_batch_exists(
                            provider_item["provider_item_uuid"],
                            provider_item["batch_no"],
                        ):
                            raise ValueError(
                                f"Item at index {idx}, provider_item at index {provider_idx}: "
                                f"batch_no '{provider_item['batch_no']}' does not exist for "
                                f"provider_item_uuid '{provider_item['provider_item_uuid']}'"
                            )


@insert_update_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "request_uuid",
    },
    model_funct=_get_request,
    count_funct=get_request_count,
    type_funct=get_request_type,
)
@purge_cache()
def insert_update_request(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    partition_key = info.context.get("partition_key")
    request_uuid = kwargs.get("request_uuid")

    # Validate items if provided (runs for both insert and update operations)
    if "items" in kwargs and kwargs["items"]:
        _validate_request_items(partition_key, kwargs["items"])

    if kwargs.get("entity") is None:
        cols = {
            "endpoint_id": info.context.get("endpoint_id"),
            "part_id": info.context.get("part_id"),
            "items": [],
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "email",
            "request_title",
            "request_description",
            "billing_address",
            "shipping_address",
            "items",
            "notes",
            "status",
            "expired_at",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]
        RequestModel(
            partition_key,
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
        "email": RequestModel.email,
        "request_title": RequestModel.request_title,
        "request_description": RequestModel.request_description,
        "billing_address": RequestModel.billing_address,
        "shipping_address": RequestModel.shipping_address,
        "items": RequestModel.items,
        "notes": RequestModel.notes,
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
        "hash_key": "partition_key",
        "range_key": "request_uuid",
    },
    model_funct=get_request,
)
@purge_cache()
def delete_request(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    quote_list = resolve_quote_list(
        info, **{"request_uuid": kwargs.get("entity").request_uuid}
    )
    if quote_list.total > 0:
        return False

    file_list = resolve_file_list(
        info, **{"request_uuid": kwargs.get("entity").request_uuid}
    )
    if file_list.total > 0:
        return False

    kwargs.get("entity").delete()
    return True
