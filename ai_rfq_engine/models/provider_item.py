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
    MapAttribute,
    NumberAttribute,
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
from ..utils.normalization import normalize_to_json
from tenacity import retry, stop_after_attempt, wait_exponential

from ..handlers.config import Config
from ..types.provider_item import ProviderItemListType, ProviderItemType
from .item_price_tier import resolve_item_price_tier_list
from .quote_item import resolve_quote_item_list


class ItemUuidIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "item_uuid-index"

    partition_key = UnicodeAttribute(hash_key=True)
    item_uuid = UnicodeAttribute(range_key=True)


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


class ProviderItemExternalIdIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "provider_item_external_id-index"

    partition_key = UnicodeAttribute(hash_key=True)
    provider_item_external_id = UnicodeAttribute(range_key=True)


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


class ProviderItemModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-provider_items"

    partition_key = UnicodeAttribute(hash_key=True)
    provider_item_uuid = UnicodeAttribute(range_key=True)
    item_uuid = UnicodeAttribute()
    provider_corp_external_id = UnicodeAttribute(default="XXXXXXXXXXXXXXXXXXXX")
    provider_item_external_id = UnicodeAttribute(null=True)
    base_price_per_uom = NumberAttribute()
    item_spec = MapAttribute(null=True)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    item_uuid_index = ItemUuidIndex()
    provider_corp_external_id_index = ProviderCorpExternalIdIndex()
    provider_item_external_id_index = ProviderItemExternalIdIndex()
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
                    entity_keys["item_uuid"] = getattr(entity, "item_uuid", None)
                    entity_keys["provider_item_uuid"] = getattr(
                        entity, "provider_item_uuid", None
                    )

                # Fallback to kwargs (for creates/deletes)
                if not entity_keys.get("item_uuid"):
                    entity_keys["item_uuid"] = kwargs.get("item_uuid")
                if not entity_keys.get("provider_item_uuid"):
                    entity_keys["provider_item_uuid"] = kwargs.get("provider_item_uuid")

                # Get partition_key from context or kwargs
                partition_key = args[0].context.get("partition_key") or kwargs.get(
                    "partition_key"
                )

                purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="provider_item",
                    context_keys=(
                        {"partition_key": partition_key} if partition_key else None
                    ),
                    entity_keys=entity_keys if entity_keys else None,
                    cascade_depth=3,
                )

                if kwargs.get("item_uuid") and partition_key:
                    purge_entity_cascading_cache(
                        args[0].context.get("logger"),
                        entity_type="provider_item",
                        context_keys={"partition_key": partition_key},
                        entity_keys={
                            "provider_item_uuid": kwargs.get("provider_item_uuid")
                        },
                        cascade_depth=3,
                        custom_options={
                            "custom_getter": "get_provider_items_by_item",
                            "custom_cache_keys": [
                                "context:partition_key",
                                "key:item_uuid",
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
    cache_name=Config.get_cache_name("models", "provider_item"),
    cache_enabled=Config.is_cache_enabled,
)
def get_provider_item(partition_key: str, provider_item_uuid: str) -> ProviderItemModel:
    return ProviderItemModel.get(partition_key, provider_item_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_provider_item(
    partition_key: str, provider_item_uuid: str
) -> ProviderItemModel:
    return ProviderItemModel.get(partition_key, provider_item_uuid)


def get_provider_item_count(partition_key: str, provider_item_uuid: str) -> int:
    return ProviderItemModel.count(
        partition_key, ProviderItemModel.provider_item_uuid == provider_item_uuid
    )


def get_provider_item_type(
    info: ResolveInfo, provider_item: ProviderItemModel
) -> ProviderItemType:
    """
    Nested resolver approach: return minimal provider_item data.
    - Do NOT embed 'item' here anymore.
    'item' is resolved lazily by ProviderItemType.resolve_item.
    """
    _ = info  # Keep for signature compatibility with decorators
    pi_dict = provider_item.__dict__["attribute_values"].copy()
    # Keep all fields including FKs - nested resolvers will handle lazy loading
    return ProviderItemType(**normalize_to_json(pi_dict))


def resolve_provider_item(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ProviderItemType | None:
    partition_key = info.context.get("partition_key")

    if "provider_item_external_id" in kwargs and kwargs["provider_item_external_id"]:
        results = ProviderItemModel.query(
            partition_key,
            None,
            ProviderItemModel.provider_item_external_id
            == kwargs["provider_item_external_id"],
        )
        try:
            provider_item = results.next()
            return get_provider_item_type(info, provider_item)
        except Exception:
            return None

    # Validate provider_item_uuid is provided
    if "provider_item_uuid" not in kwargs:
        return None

    count = get_provider_item_count(partition_key, kwargs["provider_item_uuid"])
    if count == 0:
        return None

    return get_provider_item_type(
        info,
        get_provider_item(partition_key, kwargs["provider_item_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "partition_key",
        "provider_item_uuid",
        "item_uuid",
        "provider_corp_external_id",
        "provider_item_external_id",
        "updated_at",
    ],
    list_type_class=ProviderItemListType,
    type_funct=get_provider_item_type,
)
def resolve_provider_item_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    partition_key = info.context.get("partition_key")
    item_uuid = kwargs.get("item_uuid")
    provider_corp_external_id = kwargs.get("provider_corp_external_id")
    provider_item_external_id = kwargs.get("provider_item_external_id")
    min_base_price_per_uom = kwargs.get("min_base_price_per_uom")
    max_base_price_per_uom = kwargs.get("max_base_price_per_uom")
    updated_at_gt = kwargs.get("updated_at_gt")
    updated_at_lt = kwargs.get("updated_at_lt")

    args = []
    inquiry_funct = ProviderItemModel.scan
    count_funct = ProviderItemModel.count
    if partition_key:
        range_key_condition = None

        # Build range key condition for updated_at when using updated_at_index
        if updated_at_gt is not None and updated_at_lt is not None:
            range_key_condition = ProviderItemModel.updated_at.between(
                updated_at_gt, updated_at_lt
            )
        elif updated_at_gt is not None:
            range_key_condition = ProviderItemModel.updated_at > updated_at_gt
        elif updated_at_lt is not None:
            range_key_condition = ProviderItemModel.updated_at < updated_at_lt

        args = [partition_key, range_key_condition]
        inquiry_funct = ProviderItemModel.updated_at_index.query
        count_funct = ProviderItemModel.updated_at_index.count
        if item_uuid and args[1] is None:
            count_funct = ProviderItemModel.item_uuid_index.count
            args[1] = ProviderItemModel.item_uuid == item_uuid
            inquiry_funct = ProviderItemModel.item_uuid_index.query
        elif provider_corp_external_id and args[1] is None:
            count_funct = ProviderItemModel.provider_corp_external_id_index.count
            args[1] = (
                ProviderItemModel.provider_corp_external_id == provider_corp_external_id
            )
            inquiry_funct = ProviderItemModel.provider_corp_external_id_index.query
        elif provider_item_external_id and args[1] is None:
            count_funct = ProviderItemModel.provider_item_external_id_index.count
            args[1] = (
                ProviderItemModel.provider_item_external_id == provider_item_external_id
            )
            inquiry_funct = ProviderItemModel.provider_item_external_id_index.query

    the_filters = None  # We can add filters for the query
    if (
        item_uuid
        and args[1] is not None
        and inquiry_funct != ProviderItemModel.item_uuid_index.query
    ):
        the_filters &= ProviderItemModel.item_uuid == item_uuid
    if (
        provider_corp_external_id
        and args[1] is not None
        and inquiry_funct != ProviderItemModel.provider_corp_external_id_index.query
    ):
        the_filters &= (
            ProviderItemModel.provider_corp_external_id == provider_corp_external_id
        )
    if (
        provider_item_external_id
        and args[1] is not None
        and inquiry_funct != ProviderItemModel.provider_item_external_id_index.query
    ):
        the_filters &= (
            ProviderItemModel.provider_item_external_id == provider_item_external_id
        )
    if min_base_price_per_uom:
        the_filters &= ProviderItemModel.base_price_per_uom >= min_base_price_per_uom
    if max_base_price_per_uom:
        the_filters &= ProviderItemModel.base_price_per_uom <= max_base_price_per_uom
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "provider_item_uuid",
    },
    model_funct=_get_provider_item,
    count_funct=get_provider_item_count,
    type_funct=get_provider_item_type,
)
@purge_cache()
def insert_update_provider_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    partition_key = info.context.get("partition_key")
    provider_item_uuid = kwargs.get("provider_item_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "item_spec": {},
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "item_uuid",
            "provider_corp_external_id",
            "provider_item_external_id",
            "base_price_per_uom",
            "item_spec",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]
        ProviderItemModel(
            partition_key,
            provider_item_uuid,
            **cols,
        ).save()
        return

    provider_item = kwargs.get("entity")
    actions = [
        ProviderItemModel.updated_by.set(kwargs["updated_by"]),
        ProviderItemModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to ProviderItemModel attributes
    field_map = {
        "item_uuid": ProviderItemModel.item_uuid,
        "provider_corp_external_id": ProviderItemModel.provider_corp_external_id,
        "provider_item_external_id": ProviderItemModel.provider_item_external_id,
        "base_price_per_uom": ProviderItemModel.base_price_per_uom,
        "item_spec": ProviderItemModel.item_spec,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the provider item
    provider_item.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "provider_item_uuid",
    },
    model_funct=get_provider_item,
)
@purge_cache()
def delete_provider_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    from .provider_item_batches import resolve_provider_item_batch_list

    item_price_tier_list = resolve_item_price_tier_list(
        info,
        **{
            "item_uuid": kwargs.get("entity").item_uuid,
            "provider_item_uuid": kwargs.get("entity").provider_item_uuid,
        },
    )
    if item_price_tier_list.total > 0:
        return False

    quote_item_list = resolve_quote_item_list(
        info,
        **{
            "item_uuid": kwargs.get("entity").item_uuid,
            "provider_item_uuid": kwargs.get("entity").provider_item_uuid,
        },
    )
    if quote_item_list.total > 0:
        return False

    provider_item_batch_list = resolve_provider_item_batch_list(
        info,
        **{
            "provider_item_uuid": kwargs.get("entity").provider_item_uuid,
        },
    )
    if provider_item_batch_list.total > 0:
        return False

    kwargs.get("entity").delete()
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "provider_item"),
    cache_enabled=Config.is_cache_enabled,
)
def get_provider_items_by_item(partition_key: str, item_uuid: str) -> Any:
    provider_items = []
    for provider_item in ProviderItemModel.item_uuid_index.query(
        partition_key, ProviderItemModel.item_uuid == item_uuid
    ):
        provider_items.append(provider_item)
    return provider_items
