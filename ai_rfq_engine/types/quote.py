#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

from graphene import DateTime, Field, Int, List, ObjectType, String
from silvaengine_dynamodb_base import ListObjectType
from silvaengine_utility import Debugger, JSONCamelCase
from silvaengine_utility import SafeFloat as Float

from ..models.batch_loaders import get_loaders
from ..utils.normalization import normalize_to_json


class QuoteType(ObjectType):
    request_uuid = String()  # keep raw id
    quote_uuid = String()
    partition_key = String()
    provider_corp_external_id = String()
    sales_rep_email = String()
    rounds = Int()
    shipping_method = String()
    shipping_amount = Float()
    total_quote_amount = Float()
    total_quote_discount = Float()
    final_total_quote_amount = Float()
    notes = String()
    status = String()
    expired_at = DateTime()

    # Nested resolvers: strongly-typed nested relationship
    request = Field(lambda: RequestType)

    # Nested resolvers: strongly-typed nested relationships
    quote_items = List(JSONCamelCase)
    installments = List(JSONCamelCase)

    discount_prompts = List(JSONCamelCase)

    updated_by = String()
    created_at = DateTime()
    updated_at = DateTime()

    # ------- Nested resolvers -------

    def resolve_request(parent, info):
        """Resolve nested Request for this quote using DataLoader."""
        # Case 2: already embedded
        existing = getattr(parent, "request", None)
        if isinstance(existing, dict):
            return RequestType(**existing)
        if isinstance(existing, RequestType):
            return existing

        # Case 1: need to fetch using DataLoader
        partition_key = info.context.get("partition_key")
        request_uuid = getattr(parent, "request_uuid", None)
        if not partition_key or not request_uuid:
            return None

        loaders = get_loaders(info.context)
        return loaders.request_loader.load((partition_key, request_uuid)).then(
            lambda request_dict: RequestType(**request_dict) if request_dict else None
        )

    def resolve_quote_items(parent, info):
        """Resolve nested QuoteItems for this quote."""
        # Check if already embedded
        existing = getattr(parent, "quote_items", None)
        if isinstance(existing, list):
            return [normalize_to_json(qi) for qi in existing]

        # Fetch quote items for this quote
        quote_uuid = getattr(parent, "quote_uuid", None)
        if not quote_uuid:
            return []

        loaders = get_loaders(info.context)
        return loaders.quote_item_list_loader.load(quote_uuid).then(
            lambda q_items: [normalize_to_json(qi) for qi in (q_items or [])]
        )

    def resolve_installments(parent, info):
        """Resolve nested Installments for this quote."""
        # Check if already embedded
        existing = getattr(parent, "installments", None)
        if isinstance(existing, list):
            return [normalize_to_json(inst) for inst in existing]

        # Fetch installments for this quote
        quote_uuid = getattr(parent, "quote_uuid", None)
        if not quote_uuid:
            return []

        loaders = get_loaders(info.context)
        return loaders.installment_list_loader.load(quote_uuid).then(
            lambda insts: [normalize_to_json(inst) for inst in (insts or [])]
        )

    def resolve_discount_prompts(parent, info):
        """
        Resolve discount prompts for this quote with hierarchical scopes.

        Loads prompts from:
        - GLOBAL scope (always)
        - SEGMENT scope (from request email via segment_contact lookup)
        - ITEM scope (for all unique items in quote_items)
        - PROVIDER_ITEM scope (for all unique provider items in quote_items)

        Uses the combine_all_discount_prompts utility function from models.utils
        to handle the complex Promise chaining and hierarchical loading logic.
        """
        from promise import Promise

        Debugger.info(
            variable=f"{__name__}:resolve_discount_prompts",
            stage=__name__,
        )

        # Check if already embedded
        existing = getattr(parent, "discount_prompts", None)
        if isinstance(existing, list):
            return [normalize_to_json(dp) for dp in existing]

        partition_key = info.context.get("partition_key")
        if not partition_key:
            return []

        quote_uuid = getattr(parent, "quote_uuid", None)
        request_uuid = getattr(parent, "request_uuid", None)
        if not quote_uuid or not request_uuid:
            return []

        loaders = get_loaders(info.context)

        # Load request and quote_items in parallel, then combine all prompts
        # using the utility function from models.utils
        def combine_prompts_wrapper(results):
            """
            Wrapper to unpack results and call the utility function.

            Uses the combine_all_discount_prompts utility from models.utils
            to handle the complex Promise chaining and hierarchical loading logic.

            Args:
                results: Tuple of (request_dict, quote_items) from parent Promise

            Returns:
                Promise that resolves to combined list of discount prompts
            """
            from ..models.utils import combine_all_discount_prompts

            Debugger.info(
                variable=f"{__name__}:combine_prompts_wrapper",
                stage=__name__,
            )

            request_dict, quote_items = results
            email = request_dict.get("email") if request_dict else None
            return combine_all_discount_prompts(
                partition_key, email, quote_items, loaders
            )

        # Load request and quote_items in parallel, then combine all prompts
        # using the utility function from models.utils
        return Promise.all(
            [
                loaders.request_loader.load((partition_key, request_uuid)),
                loaders.quote_item_list_loader.load(quote_uuid),
            ]
        ).then(combine_prompts_wrapper)


class QuoteListType(ListObjectType):
    quote_list = List(QuoteType)


# Bottom imports - imported after class definitions to avoid circular imports
from .request import RequestType
