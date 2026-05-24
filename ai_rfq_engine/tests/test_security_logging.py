#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import annotations

import logging

import pytest


@pytest.mark.unit
def test_sensitive_log_filter_redacts_nested_secret_values():
    from ai_rfq_engine.utils.logging_filters import SensitiveValueFilter

    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        {"config": {"auth_secret_value": "raw-secret"}, "token": "raw-token"},
        (),
        None,
    )
    SensitiveValueFilter().filter(record)
    assert record.msg["config"]["auth_secret_value"] == "***REDACTED***"
    assert record.msg["token"] == "***REDACTED***"


@pytest.mark.unit
def test_inline_auth_secret_is_rejected_by_default():
    from ai_rfq_engine.handlers.config import Config
    from ai_rfq_engine.models.external_system_config import (
        insert_update_external_system_config,
    )

    Config.ALLOW_INLINE_AUTH_SECRET_VALUE = False
    with pytest.raises(ValueError, match="auth_secret_value is disabled"):
        insert_update_external_system_config.__wrapped__.__wrapped__(
            type("Info", (), {"context": {"partition_key": "tenant"}})(),
            entity=None,
            auth_secret_value="must-not-be-stored",
            updated_by="test",
        )
