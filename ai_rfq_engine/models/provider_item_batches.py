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
    BooleanAttribute,
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
from silvaengine_utility import Utility
from tenacity import retry, stop_after_attempt, wait_exponential

from ..types.provider_item_batches import (
    ProviderItemBatchListType,
    ProviderItemBatchType,
)
from .utils import _get_item, _get_provider_item


class ItemUuidIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "item_uuid-index"

    provider_item_uuid = UnicodeAttribute(hash_key=True)
    item_uuid = UnicodeAttribute(range_key=True)


class UpdateAtIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "updated_at-index"

    provider_item_uuid = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class ProviderItemBatchModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-provider_item_batches"

    provider_item_uuid = UnicodeAttribute(hash_key=True)
    batch_no = UnicodeAttribute(range_key=True)
    item_uuid = UnicodeAttribute()
    endpoint_id = UnicodeAttribute()
    expired_at = UTCDateTimeAttribute()
    produced_at = UTCDateTimeAttribute()
    cost_per_uom = NumberAttribute()
    freight_cost_per_uom = NumberAttribute()
    additional_cost_per_uom = NumberAttribute()
    total_cost_per_uom = NumberAttribute()
    guardrail_margin_per_uom = NumberAttribute(default=0)
    guardrail_price_per_uom = NumberAttribute()
    slow_move_item = BooleanAttribute(default=False)
    in_stock = BooleanAttribute(default=True)
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    item_uuid_index = ItemUuidIndex()
    updated_at_index = UpdateAtIndex()


def create_provider_item_batch_table(logger: logging.Logger) -> bool:
    """Create the ProviderItemBatch table if it doesn't exist."""
    if not ProviderItemBatchModel.exists():
        # Create with on-demand billing (PAY_PER_REQUEST)
        ProviderItemBatchModel.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        logger.info("The ProviderItemBatch table has been created.")
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_provider_item_batch(
    provider_item_uuid: str, batch_no: str
) -> ProviderItemBatchModel:
    return ProviderItemBatchModel.get(provider_item_uuid, batch_no)


def get_provider_item_batch_count(provider_item_uuid: str, batch_no: str) -> int:
    return ProviderItemBatchModel.count(
        provider_item_uuid, ProviderItemBatchModel.batch_no == batch_no
    )


def get_provider_item_batch_type(
    info: ResolveInfo, provider_item_batch: ProviderItemBatchModel
) -> ProviderItemBatchType:
    try:
        item = _get_item(info.context["endpoint_id"], provider_item_batch.item_uuid)
        provider_item = _get_provider_item(
            info.context["endpoint_id"], provider_item_batch.provider_item_uuid
        )
        provider_item_batch: Dict = provider_item_batch.__dict__["attribute_values"]
        provider_item_batch.update(
            {
                "item": item,
                "provider_item": provider_item,
            }
        )
        provider_item_batch.pop("endpoint_id")
        provider_item_batch.pop("item_uuid")
        provider_item_batch.pop("provider_item_uuid")
    except Exception as e:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise e
    return ProviderItemBatchType(**Utility.json_normalize(provider_item_batch))


def resolve_provider_item_batch(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ProviderItemBatchType:
    return get_provider_item_batch_type(
        info,
        get_provider_item_batch(kwargs["provider_item_uuid"], kwargs["batch_no"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "provider_item_uuid",
        "batch_no",
        "item_uuid",
        "updated_at",
    ],
    list_type_class=ProviderItemBatchListType,
    type_funct=get_provider_item_batch_type,
)
def resolve_provider_item_batch_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> Any:
    provider_item_uuid = kwargs.get("provider_item_uuid")
    item_uuid = kwargs.get("item_uuid")
    endpoint_id = info.context["endpoint_id"]
    expired_at_gt = kwargs.get("expired_at_gt")
    expired_at_lt = kwargs.get("expired_at_lt")
    produced_at_gt = kwargs.get("produced_at_gt")
    produced_at_lt = kwargs.get("produced_at_lt")
    min_cost_per_uom = kwargs.get("min_cost_per_uom")
    max_cost_per_uom = kwargs.get("max_cost_per_uom")
    min_total_cost_per_uom = kwargs.get("min_total_cost_per_uom")
    max_total_cost_per_uom = kwargs.get("max_total_cost_per_uom")
    slow_move_item = kwargs.get("slow_move_item")
    in_stock = kwargs.get("in_stock")
    updated_at_gt = kwargs.get("updated_at_gt")
    updated_at_lt = kwargs.get("updated_at_lt")

    args = []
    inquiry_funct = ProviderItemBatchModel.scan
    count_funct = ProviderItemBatchModel.count
    range_key_condition = None
    if provider_item_uuid:

        # Build range key condition for updated_at when using updated_at_index
        if updated_at_gt is not None and updated_at_lt is not None:
            range_key_condition = ProviderItemBatchModel.updated_at.between(
                updated_at_gt, updated_at_lt
            )
        elif updated_at_gt is not None:
            range_key_condition = ProviderItemBatchModel.updated_at > updated_at_gt
        elif updated_at_lt is not None:
            range_key_condition = ProviderItemBatchModel.updated_at < updated_at_lt

        args = [provider_item_uuid, range_key_condition]
        inquiry_funct = ProviderItemBatchModel.updated_at_index.query
        count_funct = ProviderItemBatchModel.updated_at_index.count
        if item_uuid and args[1] is None:
            count_funct = ProviderItemBatchModel.item_uuid_index.count
            args[1] = ProviderItemBatchModel.item_uuid == item_uuid
            inquiry_funct = ProviderItemBatchModel.item_uuid_index.query

    the_filters = None  # We can add filters for the query
    if item_uuid and range_key_condition is not None:
        the_filters &= ProviderItemBatchModel.item_uuid == item_uuid
    if endpoint_id:
        the_filters &= ProviderItemBatchModel.endpoint_id == endpoint_id
    if expired_at_gt:
        the_filters &= ProviderItemBatchModel.expired_at >= expired_at_gt
    if expired_at_lt:
        the_filters &= ProviderItemBatchModel.expired_at < expired_at_lt
    if produced_at_gt:
        the_filters &= ProviderItemBatchModel.produced_at >= produced_at_gt
    if produced_at_lt:
        the_filters &= ProviderItemBatchModel.produced_at < produced_at_lt
    if min_cost_per_uom:
        the_filters &= ProviderItemBatchModel.cost_per_uom >= min_cost_per_uom
    if max_cost_per_uom:
        the_filters &= ProviderItemBatchModel.cost_per_uom <= max_cost_per_uom
    if min_total_cost_per_uom:
        the_filters &= (
            ProviderItemBatchModel.total_cost_per_uom >= min_total_cost_per_uom
        )
    if max_total_cost_per_uom:
        the_filters &= (
            ProviderItemBatchModel.total_cost_per_uom <= max_total_cost_per_uom
        )
    if slow_move_item is not None:
        the_filters &= ProviderItemBatchModel.slow_move_item == slow_move_item
    if in_stock:
        the_filters &= ProviderItemBatchModel.in_stock == in_stock
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "provider_item_uuid",
        "range_key": "batch_no",
    },
    range_key_required=True,
    model_funct=get_provider_item_batch,
    count_funct=get_provider_item_batch_count,
    type_funct=get_provider_item_batch_type,
)
def insert_update_provider_item_batch(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> None:
    provider_item_uuid = kwargs.get("provider_item_uuid")
    batch_no = kwargs.get("batch_no")
    if kwargs.get("entity") is None:
        cols = {
            "endpoint_id": info.context.get("endpoint_id"),
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "item_uuid",
            "expired_at",
            "produced_at",
            "cost_per_uom",
            "freight_cost_per_uom",
            "additional_cost_per_uom",
            "guardrail_margin_per_uom",
            "slow_move_item",
            "in_stock",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]
        cols["total_cost_per_uom"] = (
            cols.get("cost_per_uom", 0)
            + cols.get("freight_cost_per_uom", 0)
            + cols.get("additional_cost_per_uom", 0)
        )
        cols["guardrail_price_per_uom"] = cols["total_cost_per_uom"] * (
            100 + cols.get("guardrail_margin_per_uom", 0) / 100
        )

        ProviderItemBatchModel(
            provider_item_uuid,
            batch_no,
            **cols,
        ).save()
        return

    provider_item_batch = kwargs.get("entity")
    actions = [
        ProviderItemBatchModel.updated_by.set(kwargs["updated_by"]),
        ProviderItemBatchModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Map of kwargs keys to ProviderItemBatchModel attributes
    field_map = {
        "item_uuid": ProviderItemBatchModel.item_uuid,
        "expired_at": ProviderItemBatchModel.expired_at,
        "produced_at": ProviderItemBatchModel.produced_at,
        "cost_per_uom": ProviderItemBatchModel.cost_per_uom,
        "freight_cost_per_uom": ProviderItemBatchModel.freight_cost_per_uom,
        "additional_cost_per_uom": ProviderItemBatchModel.additional_cost_per_uom,
        "total_cost_per_uom": ProviderItemBatchModel.total_cost_per_uom,
        "guardrail_margin_per_uom": ProviderItemBatchModel.guardrail_margin_per_uom,
        "guardrail_price_per_uom": ProviderItemBatchModel.guardrail_price_per_uom,
        "slow_move_item": ProviderItemBatchModel.slow_move_item,
        "in_stock": ProviderItemBatchModel.in_stock,
    }

    cost_per_uom: float = provider_item_batch.cost_per_uom
    freight_cost_per_uom: float = provider_item_batch.freight_cost_per_uom
    additional_cost_per_uom: float = provider_item_batch.additional_cost_per_uom
    if "cost_per_uom" in kwargs:
        cost_per_uom = float(kwargs["cost_per_uom"])
    if "freight_cost_per_uom" in kwargs:
        freight_cost_per_uom = float(kwargs["freight_cost_per_uom"])
    if "additional_cost_per_uom" in kwargs:
        additional_cost_per_uom = float(kwargs["additional_cost_per_uom"])

    kwargs["total_cost_per_uom"] = (
        cost_per_uom + freight_cost_per_uom + additional_cost_per_uom
    )

    guardrail_margin_per_uom: float = provider_item_batch.guardrail_margin_per_uom
    if "guardrail_margin_per_uom" in kwargs:
        guardrail_margin_per_uom = float(kwargs["guardrail_margin_per_uom"])

    kwargs["guardrail_price_per_uom"] = kwargs["total_cost_per_uom"] * (
        (1 + guardrail_margin_per_uom / 100)
    )

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the provider item batch
    provider_item_batch.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "provider_item_uuid",
        "range_key": "batch_no",
    },
    model_funct=get_provider_item_batch,
)
def delete_provider_item_batch(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
