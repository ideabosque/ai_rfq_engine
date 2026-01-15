#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import functools
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
from ..types.segment_contact import SegmentContactListType, SegmentContactType


class ConsumerCorpExternalIdIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "consumer_corp_external_id-index"

    partition_key = UnicodeAttribute(hash_key=True)
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

    partition_key = UnicodeAttribute(hash_key=True)
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

    partition_key = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class SegmentContactModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-segment_contacts"

    partition_key = UnicodeAttribute(hash_key=True)
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
                    entity_keys["email"] = getattr(entity, "email", None)
                    entity_keys["partition_key"] = getattr(
                        entity, "partition_key", None
                    )

                # Fallback to kwargs (for creates/deletes)
                if not entity_keys.get("segment_uuid"):
                    entity_keys["segment_uuid"] = kwargs.get("segment_uuid")
                if not entity_keys.get("email"):
                    entity_keys["email"] = kwargs.get("email")
                if not entity_keys.get("partition_key"):
                    entity_keys["partition_key"] = kwargs.get("partition_key")

                context_keys = None

                purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="segment_contact",
                    context_keys=context_keys,
                    entity_keys=entity_keys if entity_keys else None,
                    cascade_depth=3,
                )

                partition_key = args[0].context.get("partition_key") or kwargs.get(
                    "partition_key"
                )
                if kwargs.get("segment_uuid") and partition_key:
                    purge_entity_cascading_cache(
                        args[0].context.get("logger"),
                        entity_type="segment_contact",
                        context_keys={"partition_key": partition_key},
                        entity_keys={"segment_uuid": kwargs.get("segment_uuid")},
                        cascade_depth=3,
                        custom_options={
                            "custom_getter": "get_segment_contacts_by_segment",
                            "custom_cache_keys": [
                                "context:partition_key",
                                "key:segment_uuid",
                            ],
                        },
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
    cache_name=Config.get_cache_name("models", "segment_contact"),
    cache_enabled=Config.is_cache_enabled,
)
def get_segment_contact(partition_key: str, email: str) -> SegmentContactModel:
    return SegmentContactModel.get(partition_key, email)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_segment_contact(partition_key: str, email: str) -> SegmentContactModel:
    return SegmentContactModel.get(partition_key, email)


def get_segment_contact_count(partition_key: str, email: str) -> int:
    return SegmentContactModel.count(partition_key, SegmentContactModel.email == email)


def get_segment_contact_type(
    info: ResolveInfo, segment_contact: SegmentContactModel
) -> SegmentContactType:
    """
    Nested resolver approach: return minimal segment_contact data.
    - Do NOT embed 'segment'.
    'segment' is resolved lazily by SegmentContactType.resolve_segment.
    """
    _ = info  # Keep for signature compatibility with decorators
    sc_dict = segment_contact.__dict__["attribute_values"].copy()
    # Keep all fields including FKs - nested resolvers will handle lazy loading
    return SegmentContactType(**Serializer.json_normalize(sc_dict))


def resolve_segment_contact(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> SegmentContactType | None:
    partition_key = info.context["partition_key"]
    segment_uuid = kwargs.get("segment_uuid")
    email = kwargs["email"]

    # Query using segment_uuid_index if segment_uuid is provided
    if segment_uuid:
        results = list(
            SegmentContactModel.segment_uuid_index.query(
                partition_key,
                SegmentContactModel.segment_uuid == segment_uuid,
                SegmentContactModel.email == email,
            )
        )
        if not results:
            return None
        segment_contact = results[0]
    else:
        count = get_segment_contact_count(partition_key, email)
        if count == 0:
            return None
        segment_contact = get_segment_contact(partition_key, email)

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
    partition_key = info.context.get("partition_key")

    args = []
    inquiry_funct = SegmentContactModel.scan
    count_funct = SegmentContactModel.count

    # Query by partition_key (hash key)
    if partition_key:
        args = [partition_key, None]
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
    if email and (
        inquiry_funct == SegmentContactModel.consumer_corp_external_id_index.query
        or inquiry_funct == SegmentContactModel.segment_uuid_index.query
    ):
        the_filters &= SegmentContactModel.email == email
    if contact_uuid:
        the_filters &= SegmentContactModel.contact_uuid == contact_uuid
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "email",
    },
    range_key_required=True,
    model_funct=_get_segment_contact,
    count_funct=get_segment_contact_count,
    type_funct=get_segment_contact_type,
)
@purge_cache()
def insert_update_segment_contact(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    partition_key = kwargs.get("partition_key") or info.context.get("partition_key")
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
            partition_key,
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
        "hash_key": "partition_key",
        "range_key": "email",
    },
    model_funct=get_segment_contact,
)
@purge_cache()
def delete_segment_contact(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "segment_contact"),
    cache_enabled=Config.is_cache_enabled,
)
def get_segment_contacts_by_segment(partition_key: str, segment_uuid: str) -> Any:
    segment_contacts = []
    for contact in SegmentContactModel.segment_uuid_index.query(
        partition_key, SegmentContactModel.segment_uuid == segment_uuid
    ):
        segment_contacts.append(contact)
    return segment_contacts
