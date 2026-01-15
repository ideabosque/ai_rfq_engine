#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import file
from ..types.file import FileListType, FileType


def resolve_file(info: ResolveInfo, **kwargs: Dict[str, Any]) -> FileType | None:
    return file.resolve_file(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "file"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_file_list(info: ResolveInfo, **kwargs: Dict[str, Any]) -> FileListType:
    return file.resolve_file_list(info, **kwargs)
