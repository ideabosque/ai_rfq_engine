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
from silvaengine_utility import method_cache
from silvaengine_utility.serializer import Serializer
from tenacity import retry, stop_after_attempt, wait_exponential

from ..handlers.config import Config
from ..types.segment import SegmentListType, SegmentType
from .segment_contact import resolve_segment_contact_list


class ProviderCorpExternalIdIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "provider_corp_external_id-index"

    partition_key = UnicodeAttribute(hash_key=True)
    provider_corp_external_id = UnicodeAttribute(range_key=True)


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


class SegmentModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-segments"

    partition_key = UnicodeAttribute(hash_key=True)
    segment_uuid = UnicodeAttribute(range_key=True)
    provider_corp_external_id = UnicodeAttribute(default="XXXXXXXXXXXXXXXXXXXX")
    endpoint_id = UnicodeAttribute()
    part_id = UnicodeAttribute()
    segment_name = UnicodeAttribute()
    segment_description = UnicodeAttribute(null=True)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    provider_corp_external_id_index = ProviderCorpExternalIdIndex()
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
                    entity_keys["segment_uuid"] = getattr(entity, "segment_uuid", None)

                # Fallback to kwargs (for creates/deletes)
                if not entity_keys.get("segment_uuid"):
                    entity_keys["segment_uuid"] = kwargs.get("segment_uuid")

                # Get partition_key from context or kwargs
                partition_key = args[0].context.get("partition_key") or kwargs.get(
                    "partition_key"
                )

                purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="segment",
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
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "segment"),
    cache_enabled=Config.is_cache_enabled,
)
def get_segment(partition_key: str, segment_uuid: str) -> SegmentModel:
    return SegmentModel.get(partition_key, segment_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_segment(partition_key: str, segment_uuid: str) -> SegmentModel:
    return SegmentModel.get(partition_key, segment_uuid)


def get_segment_count(partition_key: str, segment_uuid: str) -> int:
    return SegmentModel.count(partition_key, SegmentModel.segment_uuid == segment_uuid)


def get_segment_type(info: ResolveInfo, segment: SegmentModel) -> SegmentType:
    """
    Nested resolver approach: return minimal segment data.
    Those are resolved lazily by SegmentType resolvers.
    """
    _ = info  # Keep for signature compatibility with decorators
    segment_dict = segment.__dict__["attribute_values"].copy()
    # Keep all fields including FKs - nested resolvers will handle lazy loading
    return SegmentType(**Serializer.json_normalize(segment_dict))


def resolve_segment(info: ResolveInfo, **kwargs: Dict[str, Any]) -> SegmentType | None:
    partition_key = info.context.get("partition_key")
    count = get_segment_count(partition_key, kwargs["segment_uuid"])
    if count == 0:
        return None

    return get_segment_type(
        info,
        get_segment(partition_key, kwargs["segment_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "partition_key",
        "segment_uuid",
        "provider_corp_external_id",
        "updated_at",
    ],
    list_type_class=SegmentListType,
    type_funct=get_segment_type,
)
def resolve_segment_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    partition_key = info.context.get("partition_key")
    provider_corp_external_id = kwargs.get("provider_corp_external_id")
    segment_name = kwargs.get("segment_name")
    segment_description = kwargs.get("segment_description")

    args = []
    inquiry_funct = SegmentModel.scan
    count_funct = SegmentModel.count
    if partition_key:
        args = [partition_key, None]
        inquiry_funct = SegmentModel.updated_at_index.query
        count_funct = SegmentModel.updated_at_index.count
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
        "hash_key": "partition_key",
        "range_key": "segment_uuid",
    },
    model_funct=_get_segment,
    count_funct=get_segment_count,
    type_funct=get_segment_type,
)
@purge_cache()
def insert_update_segment(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    partition_key = info.context.get("partition_key")
    segment_uuid = kwargs.get("segment_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "endpoint_id": info.context.get("endpoint_id"),
            "part_id": info.context.get("part_id"),
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
            partition_key,
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
        "hash_key": "partition_key",
        "range_key": "segment_uuid",
    },
    model_funct=get_segment,
)
@purge_cache()
def delete_segment(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    segment_contact_list = resolve_segment_contact_list(
        info, **{"segment_uuid": kwargs.get("entity").segment_uuid}
    )
    if segment_contact_list.total > 0:
        return False

    kwargs.get("entity").delete()
    return True
