#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import request
from ..types.request import RequestListType, RequestType


def resolve_request(info: ResolveInfo, **kwargs: Dict[str, Any]) -> RequestType:
    return request.resolve_request(info, **kwargs)


def resolve_request_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> RequestListType:
    return request.resolve_request_list(info, **kwargs)
