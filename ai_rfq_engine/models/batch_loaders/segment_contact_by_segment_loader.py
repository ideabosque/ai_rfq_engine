#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from typing import Any, Dict, List

from promise import Promise

from ..segment_contact import SegmentContactModel
from .base import Key, SafeDataLoader, normalize_model


class SegmentContactBySegmentLoader(SafeDataLoader):
    """Batch loader returning contacts for a segment keyed by (endpoint_id, segment_uuid)."""

    def batch_load_fn(self, keys: List[Key]) -> Promise:
        unique_keys = list(dict.fromkeys(keys))
        key_map: Dict[Key, List[Dict[str, Any]]] = {}

        for endpoint_id, segment_uuid in unique_keys:
            try:
                contacts = SegmentContactModel.segment_uuid_index.query(
                    endpoint_id, SegmentContactModel.segment_uuid == segment_uuid
                )
                key_map[(endpoint_id, segment_uuid)] = [
                    normalize_model(contact) for contact in contacts
                ]
            except Exception as exc:  # pragma: no cover - defensive
                if self.logger:
                    self.logger.exception(exc)
                key_map[(endpoint_id, segment_uuid)] = []

        return Promise.resolve([key_map.get(key, []) for key in keys])
