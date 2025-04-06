#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import time
from typing import Any, Dict

from graphene import DateTime, Field, Float, Int, List, ObjectType, ResolveInfo, String

from .mutations.discount_rule import DeleteDiscountRule, InsertUpdateDiscountRule
from .mutations.file import DeleteFile, InsertUpdateFile
from .mutations.installment import DeleteInstallment, InsertUpdateInstallment
from .mutations.item import DeleteItem, InsertUpdateItem
from .mutations.item_price_tier import DeleteItemPriceTier, InsertUpdateItemPriceTier
from .mutations.provider_item import DeleteProviderItem, InsertUpdateProviderItem
from .mutations.quote import DeleteQuote, InsertUpdateQuote
from .mutations.quote_item import DeleteQuoteItem, InsertUpdateQuoteItem
from .mutations.request import DeleteRequest, InsertUpdateRequest
from .mutations.segment import DeleteSegment, InsertUpdateSegment
from .mutations.segment_contact import DeleteSegmentContact, InsertUpdateSegmentContact
from .queries.discount_rule import resolve_discount_rule, resolve_discount_rule_list
from .queries.file import resolve_file, resolve_file_list
from .queries.installment import resolve_installment, resolve_installment_list
from .queries.item import resolve_item, resolve_item_list
from .queries.item_price_tier import (
    resolve_item_price_tier,
    resolve_item_price_tier_list,
)
from .queries.provider_item import resolve_provider_item, resolve_provider_item_list
from .queries.quote import resolve_quote, resolve_quote_list
from .queries.quote_item import resolve_quote_item, resolve_quote_item_list
from .queries.request import resolve_request, resolve_request_list
from .queries.segment import resolve_segment, resolve_segment_list
from .queries.segment_contact import (
    resolve_segment_contact,
    resolve_segment_contact_list,
)
from .types.discount_rule import DiscountRuleListType, DiscountRuleType
from .types.file import FileListType, FileType
from .types.installment import InstallmentListType, InstallmentType
from .types.item import ItemListType, ItemType
from .types.item_price_tier import ItemPriceTierListType, ItemPriceTierType
from .types.provider_item import ProviderItemListType, ProviderItemType
from .types.quote import QuoteListType, QuoteType
from .types.quote_item import QuoteItemListType, QuoteItemType
from .types.request import RequestListType, RequestType
from .types.segment import SegmentListType, SegmentType
from .types.segment_contact import SegmentContactListType, SegmentContactType


def type_class():
    return [
        DiscountRuleType,
        DiscountRuleListType,
        FileType,
        FileListType,
        InstallmentType,
        InstallmentListType,
        ItemType,
        ItemListType,
        ItemPriceTierType,
        ItemPriceTierListType,
        ProviderItemType,
        ProviderItemListType,
        QuoteType,
        QuoteListType,
        QuoteItemType,
        QuoteItemListType,
        RequestType,
        RequestListType,
        SegmentType,
        SegmentListType,
        SegmentContactType,
        SegmentContactListType,
    ]


class Query(ObjectType):
    ping = String()

    item = Field(
        ItemType,
        item_uuid=String(required=True),
    )

    item_list = Field(
        ItemListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        item_type=String(required=False),
        item_name=String(required=False),
        item_description=String(required=False),
        uoms=List(String, required=False),
    )

    segment = Field(
        SegmentType,
        segment_uuid=String(required=True),
    )

    segment_list = Field(
        SegmentListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        provider_corp_external_Id=String(required=False),
        segment_name=String(required=False),
        segment_description=String(required=False),
    )

    segment_contact = Field(
        SegmentContactType,
        segment_uuid=String(required=True),
        email=String(required=True),
    )

    segment_contact_list = Field(
        SegmentContactListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        segment_uuid=String(required=False),
        contact_uuid=String(required=False),
        consumer_corp_external_id=String(required=False),
        email=String(required=False),
    )

    provider_item = Field(
        ProviderItemType,
        provider_item_uuid=String(required=True),
    )

    provider_item_list = Field(
        ProviderItemListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        item_uuid=String(required=False),
        provider_corp_external_Id=String(required=False),
        external_id=String(required=False),
        min_base_price_per_uom=Float(required=False),
        max_base_price_per_uom=Float(required=False),
    )

    item_price_tier = Field(
        ItemPriceTierType,
        item_uuid=String(required=True),
        item_price_tier_uuid=String(required=True),
    )

    item_price_tier_list = Field(
        ItemPriceTierListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        item_uuid=String(required=False),
        provider_item_uuid=String(required=False),
        segment_uuid=String(required=False),
        min_quantity_greater_then=Float(required=False),
        max_quantity_greater_then=Float(required=False),
        min_quantity_less_then=Float(required=False),
        max_quantity_less_then=Float(required=False),
        min_price=Float(required=False),
        max_price=Float(required=False),
    )

    discount_rule = Field(
        DiscountRuleType,
        item_uuid=String(required=True),
        discount_rule_uuid=String(required=True),
    )

    discount_rule_list = Field(
        DiscountRuleListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        item_uuid=String(required=False),
        provider_item_uuid=String(required=False),
        segment_uuid=String(required=False),
        max_subtotal_greater_than=Float(required=False),
        min_subtotal_greater_than=Float(required=False),
        max_subtotal_less_than=Float(required=False),
        min_subtotal_less_than=Float(required=False),
        max_discount_percentage=Float(required=False),
        min_discount_percentage=Float(required=False),
    )

    request = Field(
        RequestType,
        request_uuid=String(required=True),
    )

    request_list = Field(
        RequestListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        contact_uuid=String(required=False),
        request_title=String(required=False),
        request_description=String(required=False),
        statuses=List(String, required=False),
        from_expired_at=DateTime(required=False),
        to_expired_at=DateTime(required=False),
    )

    quote = Field(
        QuoteType,
        request_uuid=String(required=True),
        quote_uuid=String(required=True),
    )

    quote_list = Field(
        QuoteListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        request_uuid=String(required=False),
        provider_corp_external_Id=String(required=False),
        contact_uuid=String(required=False),
        shipping_methods=List(String, required=False),
        min_shipping_amount=Float(required=False),
        max_shipping_amount=Float(required=False),
        min_total_amount=Float(required=False),
        max_total_amount=Float(required=False),
        min_total_discount_percentage=Float(required=False),
        max_total_discount_percentage=Float(required=False),
        min_final_total_amount=Float(required=False),
        max_final_total_amount=Float(required=False),
        statuses=List(String, required=False),
    )

    quote_item = Field(
        QuoteItemType,
        quote_uuid=String(required=True),
        quote_item_uuid=String(required=True),
    )

    quote_item_list = Field(
        QuoteItemListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        quote_uuid=String(required=False),
        provider_item_uuid=String(required=False),
        item_uuid=String(required=False),
        request_uuid=String(required=False),
        min_price_per_uom=Float(required=False),
        max_price_per_uom=Float(required=False),
        min_qty=Float(required=False),
        max_qty=Float(required=False),
        min_subtotal=Float(required=False),
        max_subtotal=Float(required=False),
        min_discount_percentage=Float(required=False),
        max_discount_percentage=Float(required=False),
        min_final_subtotal=Float(required=False),
        max_final_subtotal=Float(required=False),
    )

    installment = Field(
        InstallmentType,
        quote_uuid=String(required=True),
        installment_uuid=String(required=True),
    )

    installment_list = Field(
        InstallmentListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        quote_uuid=String(required=False),
        request_uuid=String(required=False),
        priority=Int(required=False),
        salesorder_no=String(required=False),
        from_scheduled_date=DateTime(required=False),
        to_scheduled_date=DateTime(required=False),
        quote_item_uuid=String(required=False),
        max_installment_ratio=Float(required=False),
        min_installment_ratio=Float(required=False),
        max_installment_amount=Float(required=False),
        min_installment_amount=Float(required=False),
        statuses=List(String, required=False),
    )

    file = Field(
        FileType,
        request_uuid=String(required=True),
        file_name=String(required=True),
    )

    file_list = Field(
        FileListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        request_uuid=String(required=False),
        email=String(required=False),
    )

    def resolve_ping(self, info: ResolveInfo) -> str:
        return f"Hello at {time.strftime('%X')}!!"

    def resolve_item(self, info: ResolveInfo, **kwargs: Dict[str, Any]) -> ItemType:
        return resolve_item(info, **kwargs)

    def resolve_item_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ItemListType:
        return resolve_item_list(info, **kwargs)

    def resolve_segment(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> SegmentType:
        return resolve_segment(info, **kwargs)

    def resolve_segment_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> SegmentListType:
        return resolve_segment_list(info, **kwargs)

    def resolve_segment_contact(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> SegmentContactType:
        return resolve_segment_contact(info, **kwargs)

    def resolve_segment_contact_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> SegmentContactListType:
        return resolve_segment_contact_list(info, **kwargs)

    def resolve_provider_item(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ProviderItemType:
        return resolve_provider_item(info, **kwargs)

    def resolve_provider_item_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ProviderItemListType:
        return resolve_provider_item_list(info, **kwargs)

    def resolve_item_price_tier(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ItemPriceTierType:
        return resolve_item_price_tier(info, **kwargs)

    def resolve_item_price_tier_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ItemPriceTierListType:
        return resolve_item_price_tier_list(info, **kwargs)

    def resolve_discount_rule(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> DiscountRuleType:
        return resolve_discount_rule(info, **kwargs)

    def resolve_discount_rule_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> DiscountRuleListType:
        return resolve_discount_rule_list(info, **kwargs)

    def resolve_request(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> RequestType:
        return resolve_request(info, **kwargs)

    def resolve_request_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> RequestListType:
        return resolve_request_list(info, **kwargs)

    def resolve_quote(self, info: ResolveInfo, **kwargs: Dict[str, Any]) -> QuoteType:
        return resolve_quote(info, **kwargs)

    def resolve_quote_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> QuoteListType:
        return resolve_quote_list(info, **kwargs)

    def resolve_quote_item(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> QuoteItemType:
        return resolve_quote_item(info, **kwargs)

    def resolve_quote_item_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> QuoteItemListType:
        return resolve_quote_item_list(info, **kwargs)

    def resolve_installment(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> InstallmentType:
        return resolve_installment(info, **kwargs)

    def resolve_installment_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> InstallmentListType:
        return resolve_installment_list(info, **kwargs)

    def resolve_file(self, info: ResolveInfo, **kwargs: Dict[str, Any]) -> FileType:
        return resolve_file(info, **kwargs)

    def resolve_file_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> FileListType:
        return resolve_file_list(info, **kwargs)


class Mutations(ObjectType):
    insert_update_item = InsertUpdateItem.Field()
    delete_item = DeleteItem.Field()
    insert_update_segment = InsertUpdateSegment.Field()
    delete_segment = DeleteSegment.Field()
    insert_update_segment_contact = InsertUpdateSegmentContact.Field()
    delete_segment_contact = DeleteSegmentContact.Field()
    insert_update_provider_item = InsertUpdateProviderItem.Field()
    delete_provider_item = DeleteProviderItem.Field()
    insert_update_item_price_tier = InsertUpdateItemPriceTier.Field()
    delete_item_price_tier = DeleteItemPriceTier.Field()
    insert_update_discount_rule = InsertUpdateDiscountRule.Field()
    delete_discount_rule = DeleteDiscountRule.Field()
    insert_update_request = InsertUpdateRequest.Field()
    delete_request = DeleteRequest.Field()
    insert_update_quote = InsertUpdateQuote.Field()
    delete_quote = DeleteQuote.Field()
    insert_update_quote_item = InsertUpdateQuoteItem.Field()
    delete_quote_item = DeleteQuoteItem.Field()
    insert_update_installment = InsertUpdateInstallment.Field()
    delete_installment = DeleteInstallment.Field()
    insert_update_file = InsertUpdateFile.Field()
    delete_file = DeleteFile.Field()
