#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict

from graphene import ResolveInfo

from ..models import installment
from ..types.installment import InstallmentListType, InstallmentType


def resolve_installment(info: ResolveInfo, **kwargs: Dict[str, Any]) -> InstallmentType:
    return installment.resolve_installment(info, **kwargs)


def resolve_installment_list(
    info: ResolveInfo, **kwargs: Dict[str, Any]
) -> InstallmentListType:
    return installment.resolve_installment_list(info, **kwargs)
