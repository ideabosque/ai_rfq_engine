from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, DateTime, Field, Float, Int, List, Mutation, String

from ..models.installment import delete_installment, insert_update_installment
from ..types.installment import InstallmentType


class InsertUpdateInstallment(Mutation):
    installment = Field(InstallmentType)

    class Arguments:
        quote_uuid = String(required=True)
        installment_uuid = String(required=False)
        request_uuid = String(required=False)
        priority = Int(required=False)
        salesorder_no = String(required=False)
        scheduled_date = DateTime(required=False)
        installment_ratio = Float(required=False)
        installment_amount = Float(required=False)
        status = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(
        root: Any, info: Any, **kwargs: Dict[str, Any]
    ) -> "InsertUpdateInstallment":
        try:
            installment = insert_update_installment(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateInstallment(installment=installment)


class DeleteInstallment(Mutation):
    ok = Boolean()

    class Arguments:
        quote_uuid = String(required=True)
        installment_uuid = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteInstallment":
        try:
            ok = delete_installment(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteInstallment(ok=ok)
