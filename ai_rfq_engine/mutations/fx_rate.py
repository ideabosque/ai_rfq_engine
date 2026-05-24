# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Float, Mutation, String
from graphene import DateTime

from ..models.fx_rate import delete_fx_rate, insert_update_fx_rate
from ..types.fx_rate import FxRateType


class InsertUpdateFxRate(Mutation):
    fx_rate = Field(FxRateType)

    class Arguments:
        fx_rate_uuid = String(required=False)
        source_currency = String(required=False)
        target_currency = String(required=False)
        rate = Float(required=False)
        currency_pair_date = String(required=False)
        rate_date = DateTime(required=False)
        provider = String(required=False)
        notes = String(required=False)
        status = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateFxRate":
        try:
            fx_rate = insert_update_fx_rate(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateFxRate(fx_rate=fx_rate)


class DeleteFxRate(Mutation):
    ok = Boolean()

    class Arguments:
        fx_rate_uuid = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteFxRate":
        try:
            ok = delete_fx_rate(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteFxRate(ok=ok)