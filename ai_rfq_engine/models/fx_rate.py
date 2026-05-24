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
from tenacity import retry, stop_after_attempt, wait_exponential

from ..handlers.config import Config
from ..types.fx_rate import FxRateListType, FxRateType
from ..utils.normalization import normalize_to_json


class CurrencyPairDateIndex(LocalSecondaryIndex):
    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()
        index_name = "currency_pair_date-index"

    partition_key = UnicodeAttribute(hash_key=True)
    currency_pair_date = UnicodeAttribute(range_key=True)


class UpdateAtIndex(LocalSecondaryIndex):
    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        projection = AllProjection()
        index_name = "updated_at-index"

    partition_key = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class FxRateModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-fx_rates"

    partition_key = UnicodeAttribute(hash_key=True)
    fx_rate_uuid = UnicodeAttribute(range_key=True)
    source_currency = UnicodeAttribute()
    target_currency = UnicodeAttribute()
    rate = NumberAttribute()
    currency_pair_date = UnicodeAttribute()
    rate_date = UTCDateTimeAttribute(null=True)
    provider = UnicodeAttribute(null=True)
    notes = UnicodeAttribute(null=True)
    status = UnicodeAttribute(default="active")
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    currency_pair_date_index = CurrencyPairDateIndex()
    updated_at_index = UpdateAtIndex()


def purge_cache():
    def actual_decorator(original_function):
        @functools.wraps(original_function)
        def wrapper_function(*args, **kwargs):
            try:
                result = original_function(*args, **kwargs)
                from ..models.cache import purge_entity_cascading_cache

                entity_keys = {}
                entity = kwargs.get("entity")
                if entity:
                    entity_keys["fx_rate_uuid"] = getattr(entity, "fx_rate_uuid", None)
                if not entity_keys.get("fx_rate_uuid"):
                    entity_keys["fx_rate_uuid"] = kwargs.get("fx_rate_uuid")

                partition_key = args[0].context.get("partition_key") or kwargs.get(
                    "partition_key"
                )
                purge_entity_cascading_cache(
                    args[0].context.get("logger"),
                    entity_type="fx_rate",
                    context_keys=(
                        {"partition_key": partition_key} if partition_key else None
                    ),
                    entity_keys=entity_keys if entity_keys else None,
                    cascade_depth=1,
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
    cache_name=Config.get_cache_name("models", "fx_rate"),
    cache_enabled=Config.is_cache_enabled,
)
def get_fx_rate(partition_key: str, fx_rate_uuid: str) -> FxRateModel:
    return FxRateModel.get(partition_key, fx_rate_uuid)


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def _get_fx_rate(partition_key: str, fx_rate_uuid: str) -> FxRateModel:
    return FxRateModel.get(partition_key, fx_rate_uuid)


def get_fx_rate_count(partition_key: str, fx_rate_uuid: str) -> int:
    return FxRateModel.count(partition_key, FxRateModel.fx_rate_uuid == fx_rate_uuid)


def get_fx_rate_type(info: ResolveInfo, fx_rate: FxRateModel) -> FxRateType:
    _ = info
    fx_rate_dict = fx_rate.__dict__["attribute_values"].copy()
    return FxRateType(**normalize_to_json(fx_rate_dict))


def resolve_fx_rate(info: ResolveInfo, **kwargs: Dict[str, Any]) -> FxRateType | None:
    partition_key = info.context.get("partition_key")
    count = get_fx_rate_count(partition_key, kwargs["fx_rate_uuid"])
    if count == 0:
        return None
    return get_fx_rate_type(info, get_fx_rate(partition_key, kwargs["fx_rate_uuid"]))


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=[
        "partition_key",
        "fx_rate_uuid",
        "source_currency",
        "target_currency",
        "updated_at",
    ],
    list_type_class=FxRateListType,
    type_funct=get_fx_rate_type,
)
def resolve_fx_rate_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    partition_key = info.context.get("partition_key")
    source_currency = kwargs.get("source_currency")
    target_currency = kwargs.get("target_currency")
    status = kwargs.get("status")

    args = []
    inquiry_funct = FxRateModel.scan
    count_funct = FxRateModel.count
    if partition_key:
        args = [partition_key, None]
        inquiry_funct = FxRateModel.updated_at_index.query
        count_funct = FxRateModel.updated_at_index.count

    the_filters = None
    if source_currency:
        the_filters &= FxRateModel.source_currency == source_currency
    if target_currency:
        the_filters &= FxRateModel.target_currency == target_currency
    if status:
        the_filters &= FxRateModel.status == status
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "fx_rate_uuid",
    },
    model_funct=_get_fx_rate,
    count_funct=get_fx_rate_count,
    type_funct=get_fx_rate_type,
)
@purge_cache()
def insert_update_fx_rate(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    if kwargs.get("entity") is None:
        partition_key = kwargs.get("partition_key") or info.context.get("partition_key")
        cols = {
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "source_currency",
            "target_currency",
            "rate",
            "currency_pair_date",
            "rate_date",
            "provider",
            "notes",
            "status",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]
        FxRateModel(
            partition_key,
            kwargs["fx_rate_uuid"],
            **cols,
        ).save()
        return

    fx_rate = kwargs.get("entity")
    actions = [
        FxRateModel.updated_by.set(kwargs["updated_by"]),
        FxRateModel.updated_at.set(pendulum.now("UTC")),
    ]

    field_map = {
        "source_currency": FxRateModel.source_currency,
        "target_currency": FxRateModel.target_currency,
        "rate": FxRateModel.rate,
        "currency_pair_date": FxRateModel.currency_pair_date,
        "rate_date": FxRateModel.rate_date,
        "provider": FxRateModel.provider,
        "notes": FxRateModel.notes,
        "status": FxRateModel.status,
    }

    for key, field in field_map.items():
        if key in kwargs:
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    fx_rate.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "partition_key",
        "range_key": "fx_rate_uuid",
    },
    model_funct=get_fx_rate,
)
@purge_cache()
def delete_fx_rate(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
