# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import traceback
from typing import Any, Dict

from graphene import Boolean, Field, Mutation, String

from ..models.file import delete_file, insert_update_file
from ..types.file import FileType


class InsertUpdateFile(Mutation):
    file = Field(FileType)

    class Arguments:
        request_uuid = String(required=True)
        file_name = String(required=True)
        email = String(required=False)
        updated_by = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "InsertUpdateFile":
        try:
            file = insert_update_file(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return InsertUpdateFile(file=file)


class DeleteFile(Mutation):
    ok = Boolean()

    class Arguments:
        request_uuid = String(required=True)
        file_name = String(required=True)

    @staticmethod
    def mutate(root: Any, info: Any, **kwargs: Dict[str, Any]) -> "DeleteFile":
        try:
            ok = delete_file(info, **kwargs)
        except Exception as e:
            log = traceback.format_exc()
            info.context.get("logger").error(log)
            raise e

        return DeleteFile(ok=ok)
