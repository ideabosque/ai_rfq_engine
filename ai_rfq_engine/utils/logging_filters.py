# -*- coding: utf-8 -*-
"""Logging safeguards for values that must never be serialized in logs."""
from __future__ import annotations

import logging
import re
from typing import Any

AUTH_SECRET_VALUE_KEYS = frozenset(
    {
        "auth_secret_value",
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "password",
        "secret",
        "token",
    }
)
REDACTED = "***REDACTED***"
_TEXT_SECRET_PATTERN = re.compile(
    r"(?i)(['\"]?(?:" + "|".join(AUTH_SECRET_VALUE_KEYS) + r")['\"]?\s*[:=]\s*)(['\"])(.*?)\2"
)


def redact_sensitive_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                REDACTED
                if str(key).lower() in AUTH_SECRET_VALUE_KEYS
                else redact_sensitive_values(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive_values(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_values(item) for item in value)
    if isinstance(value, str):
        return _TEXT_SECRET_PATTERN.sub(r"\1\2" + REDACTED + r"\2", value)
    return value


class SensitiveValueFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_sensitive_values(record.msg)
        record.args = redact_sensitive_values(record.args)
        return True


def install_sensitive_value_filter(logger: logging.Logger) -> None:
    if any(isinstance(item, SensitiveValueFilter) for item in logger.filters):
        return
    logger.addFilter(SensitiveValueFilter())
