#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import file
from ..types.file import FileListType, FileType


def resolve_file(info: ResolveInfo, **kwargs: Dict[str, Any]) -> FileType:
    return file.resolve_file(info, **kwargs)


def resolve_file_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> FileListType:
    return file.resolve_file_list(info, **kwargs)
