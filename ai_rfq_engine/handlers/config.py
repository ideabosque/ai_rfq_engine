# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import logging
from typing import Any, Dict, List

import boto3

from ..models import utils


class Config:
    """
    Centralized Configuration Class
    Manages shared configuration variables across the application.
    """

    # Class attributes
    aws_lambda = None
    aws_sqs = None
    aws_s3 = None
    schemas = {}

    # Cache Configuration
    CACHE_TTL = 1800  # 30 minutes default TTL
    CACHE_ENABLED = False

    # Cache name patterns for different modules
    CACHE_NAMES = {
        "models": "ai_rfq_engine.models",
        "queries": "ai_rfq_engine.queries",
    }

    # Cache entity metadata (module paths, getters, cache key templates)
    CACHE_ENTITY_CONFIG = {
        "request": {
            "module": "ai_rfq_engine.models.request",
            "model_class": "RequestModel",
            "getter": "get_request",
            "list_resolver": "ai_rfq_engine.queries.request.resolve_request_list",
            "cache_keys": ["context:partition_key", "key:request_uuid"],
        },
        "quote": {
            "module": "ai_rfq_engine.models.quote",
            "model_class": "QuoteModel",
            "getter": "get_quote",
            "list_resolver": "ai_rfq_engine.queries.quote.resolve_quote_list",
            "cache_keys": ["key:request_uuid", "key:quote_uuid"],
        },
        "quote_item": {
            "module": "ai_rfq_engine.models.quote_item",
            "model_class": "QuoteItemModel",
            "getter": "get_quote_item",
            "list_resolver": "ai_rfq_engine.queries.quote_item.resolve_quote_item_list",
            "cache_keys": ["key:quote_uuid", "key:quote_item_uuid"],
        },
        "segment": {
            "module": "ai_rfq_engine.models.segment",
            "model_class": "SegmentModel",
            "getter": "get_segment",
            "list_resolver": "ai_rfq_engine.queries.segment.resolve_segment_list",
            "cache_keys": ["context:partition_key", "key:segment_uuid"],
        },
        "segment_contact": {
            "module": "ai_rfq_engine.models.segment_contact",
            "model_class": "SegmentContactModel",
            "getter": "get_segment_contact",
            "list_resolver": "ai_rfq_engine.queries.segment_contact.resolve_segment_contact_list",
            "cache_keys": ["key:segment_uuid", "key:email"],
        },
        "item": {
            "module": "ai_rfq_engine.models.item",
            "model_class": "ItemModel",
            "getter": "get_item",
            "list_resolver": "ai_rfq_engine.queries.item.resolve_item_list",
            "cache_keys": ["context:partition_key", "key:item_uuid"],
        },
        "provider_item": {
            "module": "ai_rfq_engine.models.provider_item",
            "model_class": "ProviderItemModel",
            "getter": "get_provider_item",
            "list_resolver": "ai_rfq_engine.queries.provider_item.resolve_provider_item_list",
            "cache_keys": ["key:item_uuid", "key:provider_item_uuid"],
        },
        "provider_item_batch": {
            "module": "ai_rfq_engine.models.provider_item_batches",
            "model_class": "ProviderItemBatchModel",
            "getter": "get_provider_item_batch",
            "list_resolver": "ai_rfq_engine.queries.provider_item_batches.resolve_provider_item_batch_list",
            "cache_keys": ["key:provider_item_uuid", "key:batch_no"],
        },
        "item_price_tier": {
            "module": "ai_rfq_engine.models.item_price_tier",
            "model_class": "ItemPriceTierModel",
            "getter": "get_item_price_tier",
            "list_resolver": "ai_rfq_engine.queries.item_price_tier.resolve_item_price_tier_list",
            "cache_keys": ["key:item_uuid", "key:item_price_tier_uuid"],
        },
        "installment": {
            "module": "ai_rfq_engine.models.installment",
            "model_class": "InstallmentModel",
            "getter": "get_installment",
            "list_resolver": "ai_rfq_engine.queries.installment.resolve_installment_list",
            "cache_keys": ["key:quote_uuid", "key:installment_uuid"],
        },
        "file": {
            "module": "ai_rfq_engine.models.file",
            "model_class": "FileModel",
            "getter": "get_file",
            "list_resolver": "ai_rfq_engine.queries.file.resolve_file_list",
            "cache_keys": ["key:request_uuid", "key:file_uuid"],
        },
        "discount_prompt": {
            "module": "ai_rfq_engine.models.discount_prompt",
            "model_class": "DiscountPromptModel",
            "getter": "get_discount_prompt",
            "list_resolver": "ai_rfq_engine.queries.discount_prompt.resolve_discount_prompt_list",
            "cache_keys": ["context:partition_key", "key:discount_prompt_uuid"],
        },
    }

    @classmethod
    def get_cache_entity_config(cls) -> Dict[str, Dict[str, Any]]:
        """Get cache configuration metadata for each entity type."""
        return cls.CACHE_ENTITY_CONFIG

    # Entity cache dependency relationships
    CACHE_RELATIONSHIPS = {
        "request": [
            {
                "entity_type": "quote",
                "list_resolver": "resolve_quote_list",
                "module": "quote",
                "dependency_key": "request_uuid",
            },
            {
                "entity_type": "file",
                "list_resolver": "resolve_file_list",
                "module": "file",
                "dependency_key": "request_uuid",
            },
        ],
        "quote": [
            {
                "entity_type": "quote_item",
                "list_resolver": "resolve_quote_item_list",
                "module": "quote_item",
                "dependency_key": "quote_uuid",
            },
            {
                "entity_type": "installment",
                "list_resolver": "resolve_installment_list",
                "module": "installment",
                "dependency_key": "quote_uuid",
            },
        ],
        "segment": [
            {
                "entity_type": "segment_contact",
                "list_resolver": "resolve_segment_contact_list",
                "module": "segment_contact",
                "dependency_key": "segment_uuid",
            },
            {
                "entity_type": "item_price_tier",
                "list_resolver": "resolve_item_price_tier_list",
                "module": "item_price_tier",
                "dependency_key": "segment_uuid",
            },
            {
                "entity_type": "discount_prompt",
                "list_resolver": "resolve_discount_prompt_list",
                "module": "discount_prompt",
                "dependency_key": "segment_uuid",
            },
        ],
        "item": [
            {
                "entity_type": "provider_item",
                "list_resolver": "resolve_provider_item_list",
                "module": "provider_item",
                "dependency_key": "item_uuid",
            },
            {
                "entity_type": "item_price_tier",
                "list_resolver": "resolve_item_price_tier_list",
                "module": "item_price_tier",
                "dependency_key": "item_uuid",
            },
            {
                "entity_type": "discount_prompt",
                "list_resolver": "resolve_discount_prompt_list",
                "module": "discount_prompt",
                "dependency_key": "item_uuid",
            },
        ],
        "provider_item": [
            {
                "entity_type": "provider_item_batch",
                "list_resolver": "resolve_provider_item_batch_list",
                "module": "provider_item_batches",
                "dependency_key": "provider_item_uuid",
            },
            {
                "entity_type": "item_price_tier",
                "list_resolver": "resolve_item_price_tier_list",
                "module": "item_price_tier",
                "dependency_key": "provider_item_uuid",
            },
            {
                "entity_type": "discount_prompt",
                "list_resolver": "resolve_discount_prompt_list",
                "module": "discount_prompt",
                "dependency_key": "provider_item_uuid",
            },
        ],
    }

    # Public methods
    @classmethod
    def initialize(cls, logger: logging.Logger, **setting: Dict[str, Any]) -> None:
        """
        Initialize configuration setting.
        Args:
            logger (logging.Logger): Logger instance for logging.
            **setting (Dict[str, Any]): Configuration dictionary.
        """
        try:
            cls._set_parameters(setting)
            cls._initialize_aws_services(setting)
            if setting.get("initialize_tables"):
                cls._initialize_tables(logger)
            logger.info("Configuration initialized successfully.")
        except Exception as e:
            logger.exception("Failed to initialize configuration.")
            raise e

    # Private methods
    @classmethod
    def _set_parameters(cls, setting: Dict[str, Any]) -> None:
        """
        Set application-level parameters.
        Args:
            setting (Dict[str, Any]): Configuration dictionary.
        """
        cls.source_email = setting.get("source_email")

        # Set cache enabled flag (defaults to True if not specified)
        # if "cache_enabled" in setting:
        #     cls.CACHE_ENABLED = setting.get("cache_enabled", True)

    @classmethod
    def _initialize_aws_services(cls, setting: Dict[str, Any]) -> None:
        """
        Initialize AWS services, such as the S3 client.
        Args:
            setting (Dict[str, Any]): Configuration dictionary.
        """
        if all(
            setting.get(k)
            for k in ["region_name", "aws_access_key_id", "aws_secret_access_key"]
        ):
            aws_credentials = {
                "region_name": setting["region_name"],
                "aws_access_key_id": setting["aws_access_key_id"],
                "aws_secret_access_key": setting["aws_secret_access_key"],
            }
        else:
            aws_credentials = {}

        cls.aws_lambda = boto3.client("lambda", **aws_credentials)
        cls.aws_sqs = boto3.resource("sqs", **aws_credentials)
        cls.aws_s3 = boto3.client(
            "s3",
            **aws_credentials,
            config=boto3.session.Config(signature_version="s3v4"),
        )

    @classmethod
    def _initialize_tables(cls, logger: logging.Logger) -> None:
        """
        Initialize database tables by calling the utils.initialize_tables() method.
        This is an internal method used during configuration setup.
        """
        utils.initialize_tables(logger)

    @classmethod
    def get_cache_name(cls, module_type: str, model_name: str) -> str:
        """
        Generate standardized cache names.

        Args:
            module_type: 'models' or 'queries'
            model_name: Name of the model (e.g., 'request', 'quote')

        Returns:
            Standardized cache name string
        """
        base_name = cls.CACHE_NAMES.get(module_type, f"ai_rfq_engine.{module_type}")
        return f"{base_name}.{model_name}"

    @classmethod
    def get_cache_ttl(cls) -> int:
        """Get the configured cache TTL."""
        return cls.CACHE_TTL

    @classmethod
    def is_cache_enabled(cls) -> bool:
        """Check if caching is enabled."""
        return cls.CACHE_ENABLED

    @classmethod
    def get_cache_relationships(cls) -> Dict[str, List[Dict[str, str]]]:
        """Get entity cache dependency relationships."""
        return cls.CACHE_RELATIONSHIPS

    @classmethod
    def get_entity_children(cls, entity_type: str) -> List[Dict[str, str]]:
        """Get child entities for a specific entity type."""
        return cls.CACHE_RELATIONSHIPS.get(entity_type, [])
