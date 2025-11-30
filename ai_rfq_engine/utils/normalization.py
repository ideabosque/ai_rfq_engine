#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any

from silvaengine_utility import Utility


def normalize_to_json(item: Any) -> Any:
    """Convert model objects or plain objects into JSON-serializable data."""
    if isinstance(item, dict):
        return Utility.json_normalize(item)
    if hasattr(item, "attribute_values"):
        return Utility.json_normalize(item.attribute_values)
    if hasattr(item, "__dict__"):
        return Utility.json_normalize(
            {k: v for k, v in vars(item).items() if not k.startswith("_")}
        )
    return item
