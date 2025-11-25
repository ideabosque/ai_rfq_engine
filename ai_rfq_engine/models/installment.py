#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
import traceback
from typing import Any, Dict

import pendulum
from graphene import ResolveInfo
from pynamodb.attributes import NumberAttribute, UnicodeAttribute, UTCDateTimeAttribute
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

from ..types.installment import InstallmentListType, InstallmentType
from .utils import _get_quote


class UpdateAtIndex(LocalSecondaryIndex):
    """
    This class represents a local secondary index
    """

    class Meta:
        billing_mode = "PAY_PER_REQUEST"
        # All attributes are projected
        projection = AllProjection()
        index_name = "updated_at-index"

    quote_uuid = UnicodeAttribute(hash_key=True)
    updated_at = UnicodeAttribute(range_key=True)


class InstallmentModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-installments"

    quote_uuid = UnicodeAttribute(hash_key=True)
    installment_uuid = UnicodeAttribute(range_key=True)
    endpoint_id = UnicodeAttribute()
    request_uuid = UnicodeAttribute()
    priority = NumberAttribute(default=0)
    salesorder_no = UnicodeAttribute(null=True)
    payment_method = UnicodeAttribute()
    scheduled_date = UTCDateTimeAttribute(null=True)
    installment_ratio = NumberAttribute(default=0)
    installment_amount = NumberAttribute(default=0)
    status = UnicodeAttribute(default="pending")
    created_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()
    updated_at = UTCDateTimeAttribute()
    updated_at_index = UpdateAtIndex()


def create_installment_table(logger: logging.Logger) -> bool:
    """Create the Installment table if it doesn't exist."""
    if not InstallmentModel.exists():
        # Create with on-demand billing (PAY_PER_REQUEST)
        InstallmentModel.create_table(billing_mode="PAY_PER_REQUEST", wait=True)
        logger.info("The Installment table has been created.")
    return True


@retry(
    reraise=True,
    wait=wait_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(5),
)
def get_installment(quote_uuid: str, installment_uuid: str) -> InstallmentModel:
    return InstallmentModel.get(quote_uuid, installment_uuid)


def get_installment_count(quote_uuid: str, installment_uuid: str) -> int:
    return InstallmentModel.count(
        quote_uuid, InstallmentModel.installment_uuid == installment_uuid
    )


def _calculate_installment_ratio(
    info: ResolveInfo,
    request_uuid: str,
    quote_uuid: str,
    installment_amount: float,
) -> float | None:
    """
    Calculate installment_ratio based on installment_amount and quote's final_total_quote_amount.

    Args:
        info: GraphQL resolve info containing logger
        request_uuid: The request UUID
        quote_uuid: The quote UUID
        installment_amount: The installment amount

    Returns:
        The calculated installment_ratio as a percentage, or None if calculation fails
    """
    try:
        quote = _get_quote(request_uuid, quote_uuid)
        if quote["final_total_quote_amount"] and quote["final_total_quote_amount"] > 0:
            return (
                float(installment_amount) / float(quote["final_total_quote_amount"])
            ) * 100
    except Exception as e:
        info.context.get("logger").warning(
            f"Failed to calculate installment_ratio: {str(e)}"
        )
    return None


def get_installment_type(
    info: ResolveInfo, installment: InstallmentModel
) -> InstallmentType:
    """
    Nested resolver approach: return minimal installment data.
    - Do NOT embed 'quote'.
    'quote' is resolved lazily by InstallmentType.resolve_quote.
    """
    try:
        inst_dict = installment.__dict__["attribute_values"]
    except Exception:
        log = traceback.format_exc()
        info.context.get("logger").exception(log)
        raise

    return InstallmentType(**Utility.json_normalize(inst_dict))


def resolve_installment(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> InstallmentType | None:
    count = get_installment_count(kwargs["quote_uuid"], kwargs["installment_uuid"])
    if count == 0:
        return None

    return get_installment_type(
        info,
        get_installment(kwargs["quote_uuid"], kwargs["installment_uuid"]),
    )


@monitor_decorator
@resolve_list_decorator(
    attributes_to_get=["quote_uuid", "installment_uuid", "updated_at"],
    list_type_class=InstallmentListType,
    type_funct=get_installment_type,
)
def resolve_installment_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> Any:
    quote_uuid = kwargs.get("quote_uuid")
    request_uuid = kwargs.get("request_uuid")
    endpoint_id = info.context.get("endpoint_id")
    priority = kwargs.get("priority")
    salesorder_no = kwargs.get("salesorder_no")
    from_scheduled_date = kwargs.get("from_scheduled_date")
    to_scheduled_date = kwargs.get("to_scheduled_date")
    max_installment_ratio = kwargs.get("max_installment_ratio")
    min_installment_ratio = kwargs.get("min_installment_ratio")
    max_installment_amount = kwargs.get("max_installment_amount")
    min_installment_amount = kwargs.get("min_installment_amount")
    statuses = kwargs.get("statuses")
    updated_at_gt = kwargs.get("updated_at_gt")
    updated_at_lt = kwargs.get("updated_at_lt")

    args = []
    inquiry_funct = InstallmentModel.scan
    count_funct = InstallmentModel.count
    range_key_condition = None
    if quote_uuid:

        # Build range key condition for updated_at when using updated_at_index
        if updated_at_gt is not None and updated_at_lt is not None:
            range_key_condition = InstallmentModel.updated_at.between(
                updated_at_gt, updated_at_lt
            )
        elif updated_at_gt is not None:
            range_key_condition = InstallmentModel.updated_at > updated_at_gt
        elif updated_at_lt is not None:
            range_key_condition = InstallmentModel.updated_at < updated_at_lt

        args = [quote_uuid, range_key_condition]
        inquiry_funct = InstallmentModel.updated_at_index.query
        count_funct = InstallmentModel.updated_at_index.count

    the_filters = None
    if endpoint_id:
        the_filters = InstallmentModel.endpoint_id == endpoint_id
    if request_uuid:
        the_filters &= InstallmentModel.request_uuid == request_uuid
    if priority:
        the_filters &= InstallmentModel.priority == priority
    if salesorder_no:
        the_filters &= InstallmentModel.salesorder_no == salesorder_no
    if from_scheduled_date and to_scheduled_date:
        the_filters &= InstallmentModel.scheduled_date.between(
            from_scheduled_date, to_scheduled_date
        )
    if max_installment_ratio and min_installment_ratio:
        the_filters &= InstallmentModel.installment_ratio.exists()
        the_filters &= InstallmentModel.installment_ratio.between(
            min_installment_ratio, max_installment_ratio
        )
    if max_installment_amount and min_installment_amount:
        the_filters &= InstallmentModel.installment_amount.exists()
        the_filters &= InstallmentModel.installment_amount.between(
            min_installment_amount, max_installment_amount
        )
    if statuses:
        the_filters &= InstallmentModel.status.is_in(*statuses)
    if the_filters is not None:
        args.append(the_filters)

    return inquiry_funct, count_funct, args


@insert_update_decorator(
    keys={
        "hash_key": "quote_uuid",
        "range_key": "installment_uuid",
    },
    model_funct=get_installment,
    count_funct=get_installment_count,
    type_funct=get_installment_type,
)
def insert_update_installment(info: ResolveInfo, **kwargs: Dict[str, Any]) -> None:
    quote_uuid = kwargs.get("quote_uuid")
    installment_uuid = kwargs.get("installment_uuid")
    if kwargs.get("entity") is None:
        cols = {
            "endpoint_id": info.context.get("endpoint_id"),
            "request_uuid": kwargs.get("request_uuid"),
            "updated_by": kwargs["updated_by"],
            "created_at": pendulum.now("UTC"),
            "updated_at": pendulum.now("UTC"),
        }
        for key in [
            "priority",
            "salesorder_no",
            "payment_method",
            "scheduled_date",
            "installment_amount",
            "status",
        ]:
            if key in kwargs:
                cols[key] = kwargs[key]

        # Calculate installment_ratio if installment_amount is provided
        if "installment_amount" in cols and cols["installment_amount"] is not None:
            calculated_ratio = _calculate_installment_ratio(
                info, kwargs.get("request_uuid"), quote_uuid, cols["installment_amount"]
            )
            if calculated_ratio is not None:
                cols["installment_ratio"] = calculated_ratio

        InstallmentModel(
            quote_uuid,
            installment_uuid,
            **cols,
        ).save()
        return

    installment = kwargs.get("entity")
    actions = [
        InstallmentModel.updated_by.set(kwargs["updated_by"]),
        InstallmentModel.updated_at.set(pendulum.now("UTC")),
    ]

    # Calculate installment_ratio if installment_amount is being updated
    if "installment_amount" in kwargs and kwargs["installment_amount"] is not None:
        calculated_ratio = _calculate_installment_ratio(
            info, installment.request_uuid, quote_uuid, kwargs["installment_amount"]
        )
        if calculated_ratio is not None:
            # Apply the calculated installment_ratio
            actions.append(InstallmentModel.installment_ratio.set(calculated_ratio))

    # Map of kwargs keys to InstallmentModel attributes
    field_map = {
        "request_uuid": InstallmentModel.request_uuid,
        "priority": InstallmentModel.priority,
        "salesorder_no": InstallmentModel.salesorder_no,
        "payment_method": InstallmentModel.payment_method,
        "scheduled_date": InstallmentModel.scheduled_date,
        "installment_amount": InstallmentModel.installment_amount,
        "status": InstallmentModel.status,
    }

    # Add actions dynamically based on the presence of keys in kwargs
    for key, field in field_map.items():
        if key in kwargs:  # Check if the key exists in kwargs
            actions.append(field.set(None if kwargs[key] == "null" else kwargs[key]))

    # Update the installment
    installment.update(actions=actions)
    return


@delete_decorator(
    keys={
        "hash_key": "quote_uuid",
        "range_key": "installment_uuid",
    },
    model_funct=get_installment,
)
def delete_installment(info: ResolveInfo, **kwargs: Dict[str, Any]) -> bool:
    kwargs.get("entity").delete()
    return True
