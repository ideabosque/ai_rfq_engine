#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List

from promise import Promise

from ..file import FileModel
from .base import SafeDataLoader, normalize_model


class FilesByRequestLoader(SafeDataLoader):
    """Batch loader returning all files for a request keyed by request_uuid."""

    def batch_load_fn(self, keys: List[str]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[str, List[Dict[str, Any]]] = {}

        for request_uuid in unique_keys:
            try:
                files = FileModel.query(request_uuid)
                key_map[request_uuid] = [normalize_model(f) for f in files]
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[request_uuid] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])
