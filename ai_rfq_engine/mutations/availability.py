# -*- coding: utf-8 -*-
from __future__ import annotations

import traceback
from typing import Any, Dict

from graphene import DateTime, Field, Mutation, String
from silvaengine_utility import JSONCamelCase
from silvaengine_utility import SafeFloat as Float

from ..handlers.availability import (
    dispatch_acquire_hold,
    dispatch_confirm_hold,
    dispatch_expire_hold,
    dispatch_release_hold,
)
from ..queries.availability import _result_from_dispatch
from ..types.availability import AvailabilityResultType


class AcquireAvailabilityHold(Mutation):
    availability = Field(AvailabilityResultType)

    class Arguments:
        provider_item_uuid = String(required=True)
        batch_no = String(required=False)
        service_start_at = DateTime(required=True)
        service_end_at = DateTime(required=True)
        pax_breakdown = JSONCamelCase(required=False)
        qty = Float(required=False)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "AcquireAvailabilityHold":
        try:
            result = _result_from_dispatch(info, dispatch_acquire_hold, **kwargs)
        except Exception:
            info.context.get("logger").error(traceback.format_exc())
            raise
        return AcquireAvailabilityHold(availability=result)


class _HeldAvailabilityMutation(Mutation):
    availability = Field(AvailabilityResultType)
    dispatcher = None

    class Arguments:
        provider_item_uuid = String(required=True)
        batch_no = String(required=False)
        hold_token = String(required=True)

    @classmethod
    def mutate(cls, root: Any, info: Any, **kwargs: Dict[str, Any]):
        try:
            result = _result_from_dispatch(info, cls.dispatcher, **kwargs)
        except Exception:
            info.context.get("logger").error(traceback.format_exc())
            raise
        return cls(availability=result)


class ReleaseAvailabilityHold(_HeldAvailabilityMutation):
    dispatcher = dispatch_release_hold


class ConfirmAvailabilityHold(_HeldAvailabilityMutation):
    dispatcher = dispatch_confirm_hold


class ExpireAvailabilityHold(_HeldAvailabilityMutation):
    dispatcher = dispatch_expire_hold
