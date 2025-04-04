# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
from typing import Any, Dict, List


def _initialize_tables(logger: logging.Logger) -> None:
    from .discount_rule import create_discount_rule_table
    from .file import create_file_table
    from .installment import create_installment_table
    from .item import create_item_table
    from .item_price_tier import create_item_price_tier_table
    from .provider_item import create_provider_item_table
    from .quote import create_quote_table
    from .quote_item import create_quote_item_table
    from .request import create_request_table
    from .segment import create_segment_table
    from .segment_contact import create_segment_contact_table

    create_item_table(logger)
    create_provider_item_table(logger)
    create_item_price_tier_table(logger)
    create_segment_table(logger)
    create_segment_contact_table(logger)
    create_quote_table(logger)
    create_quote_item_table(logger)
    create_request_table(logger)
    create_file_table(logger)
    create_installment_table(logger)
    create_discount_rule_table(logger)
    return
