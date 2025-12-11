#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, Tuple

from promise.dataloader import DataLoader
from silvaengine_utility import Utility

from ...handlers.config import Config

# Type aliases for readability
Key = Tuple[str, str]


def normalize_model(model: Any) -> Dict[str, Any]:
    """Safely convert a Pynamo model into a plain dict."""
    return Utility.json_normalize(model.__dict__["attribute_values"])


class SafeDataLoader(DataLoader):
    """
    Base DataLoader that swallows and logs errors rather than breaking the entire
    request. This keeps individual load failures isolated.
    """

    def __init__(self, logger=None, cache_enabled=True, **kwargs):
        super(SafeDataLoader, self).__init__(**kwargs)
        self.logger = logger
        self.cache_enabled = cache_enabled and Config.is_cache_enabled()

    def dispatch(self):
        try:
            return super(SafeDataLoader, self).dispatch()
        except Exception as exc:  # pragma: no cover - defensive
            if self.logger:
                self.logger.exception(exc)
            raise
