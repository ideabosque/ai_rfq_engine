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
from silvaengine_utility import Utility, method_cache
from tenacity import retry, stop_after_attempt, wait_exponential

from ..handlers.config import Config
from ..types.provider_item import ProviderItemListType, ProviderItemType
from .discount_rule import resolve_discount_rule_list
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

    endpoint_id = UnicodeAttribute(hash_key=True)
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

    endpoint_id = UnicodeAttribute(hash_key=True)
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

    endpoint_id = UnicodeAttribute(hash_key=True)
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

    endpoint_id = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class ProviderItemModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-provider_items"

    endpoint_id = UnicodeAttribute(hash_key=True)
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
                # Use cascading cache purging for provider_items
                from ..models.cache import purge_entity_cascading_cache

                context_keys = None
                entity_keys = {}
                if kwargs.get("item_uuid"):
                    entity_keys["item_uuid"] = kwargs.get("item_uuid")
                if kwargs.get("provider_item_uuid"):
                    entity_keys["provider_item_uuid"] = kwargs.get("provider_item_uuid")

                result = purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="provider_item",
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


def create_provider_item_table(logger: logging.Logger) -> bool:
    """Create the ProviderItem table if it doesn't exist."""
    if not ProviderItemModel.exists():
        # Create with on-demand billing (PAY_PER_REQUEST)
        ProviderItemModel.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        logger.info("The ProviderItem table has been created.")
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("models", "provider_item"),
)
def get_provider_item(endpoint_id: str, provider_item_uuid: str) -> ProviderItemModel:
    return ProviderItemModel.get(endpoint_id, provider_item_uuid)


def get_provider_item_count(endpoint_id: str, provider_item_uuid: str) -> int:
    return ProviderItemModel.count(
        endpoint_id, ProviderItemModel.provider_item_uuid == provider_item_uuid
    )


def get_provider_item_type(
    info: ResolveInfo, provider_item: ProviderItemModel
) -> ProviderItemType:
    """
    Nested resolver approach: return minimal provider_item data.
    - Do NOT embed 'item' here anymore.
    'item' is resolved lazily by ProviderItemType.resolve_item.
    """
    try:
        pi_dict = provider_item.__dict__["attribute_values"]
    except Exception:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise

    return ProviderItemType(**Utility.json_normalize(pi_dict))


def resolve_provider_item(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ProviderItemType | None:
    count = get_provider_item_count(
        info.context["endpoint_id"], kwargs["provider_item_uuid"]
    )
    if count == 0:
        return None

    return get_provider_item_type(
        info,
        get_provider_item(info.context["endpoint_id"], kwargs["provider_item_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "endpoint_id",
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
    endpoint_id = info.context["endpoint_id"]
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
    if endpoint_id:
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

        args = [endpoint_id, range_key_condition]
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


@purge_cache()
@insert_update_decorator(
    keys={
        "hash_key": "endpoint_id",
        "range_key": "provider_item_uuid",
    },
    model_funct=get_provider_item,
    count_funct=get_provider_item_count,
    type_funct=get_provider_item_type,
)
def insert_update_provider_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    endpoint_id = kwargs.get("endpoint_id")
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
            endpoint_id,
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


@purge_cache()
@delete_decorator(
    keys={
        "hash_key": "endpoint_id",
        "range_key": "provider_item_uuid",
    },
    model_funct=get_provider_item,
)
def delete_provider_item(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    from .provider_item_batches import resolve_provider_item_batch_list

    discount_rule_list = resolve_discount_rule_list(
        info,
        **{
            "item_uuid": kwargs.get("entity").item_uuid,
            "provider_item_uuid": kwargs.get("entity").provider_item_uuid,
        },
    )
    if discount_rule_list.total > 0:
        return False

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
