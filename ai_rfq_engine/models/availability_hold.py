#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Durable temporary reservations for capacity-constrained provider items."""
from __future__ import annotations

from pynamodb.attributes import NumberAttribute, UnicodeAttribute, UTCDateTimeAttribute
from silvaengine_dynamodb_base import BaseModel


class AvailabilityHoldModel(BaseModel):
    class Meta(BaseModel.Meta):
        table_name = "are-availability_holds"

    HELD = "held"
    CONFIRMED = "confirmed"
    RELEASED = "released"
    EXPIRED = "expired"

    partition_key = UnicodeAttribute(hash_key=True)
    hold_token = UnicodeAttribute(range_key=True)
    provider_item_uuid = UnicodeAttribute()
    batch_no = UnicodeAttribute()
    quote_uuid = UnicodeAttribute(null=True)
    quote_item_uuid = UnicodeAttribute(null=True)
    qty = NumberAttribute()
    service_start_at = UTCDateTimeAttribute()
    service_end_at = UTCDateTimeAttribute()
    status = UnicodeAttribute(default=HELD)
    expires_at = UTCDateTimeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()
    updated_by = UnicodeAttribute()

