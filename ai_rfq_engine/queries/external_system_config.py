# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo
from silvaengine_utility import method_cache

from ..handlers.config import Config
from ..models import external_system_config
from ..types.external_system_config import (
    ExternalSystemConfigListType,
    ExternalSystemConfigType,
)


def resolve_external_system_config(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ExternalSystemConfigType | None:
    return external_system_config.resolve_external_system_config(info, **kwargs)


@method_cache(
    ttl=Config.get_cache_ttl(),
    cache_name=Config.get_cache_name("queries", "external_system_config"),
    cache_enabled=Config.is_cache_enabled,
)
def resolve_external_system_config_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ExternalSystemConfigListType:
    return external_system_config.resolve_external_system_config_list(info, **kwargs)


def resolve_external_system_for(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> ExternalSystemConfigType | None:
    return external_system_config.resolve_external_system_for(info, **kwargs)
