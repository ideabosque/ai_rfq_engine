#!/usr/bin/python
# -*- coding: utf-8 -*-
from __future__ import print_function

__author__ = "bibow"

import time
from typing import Any, Dict
from typing import List as List_Type

from graphene import (
    Boolean,
    DateTime,
    Field,
    Int,
    List,
    ObjectType,
    ResolveInfo,
    String,
)
from silvaengine_utility import JSONCamelCase
from silvaengine_utility import SafeFloat as Float

from .mutations.cancellation_policy import (
    DeleteCancellationPolicy,
    InsertUpdateCancellationPolicy,
)
from .mutations.bundle import DeleteBundle, InsertUpdateBundle
from .mutations.bundle_component import (
    DeleteBundleComponent,
    InsertUpdateBundleComponent,
)
from .mutations.fx_rate import DeleteFxRate, InsertUpdateFxRate
from .mutations.item_catalog_ref import (
    DeleteItemCatalogRef,
    InsertUpdateItemCatalogRef,
)
from .mutations.file import DeleteFile, InsertUpdateFile
from .mutations.installment import DeleteInstallment, InsertUpdateInstallment
from .mutations.item import DeleteItem, InsertUpdateItem
from .mutations.item_price_tier import DeleteItemPriceTier, InsertUpdateItemPriceTier
from .mutations.provider_item import DeleteProviderItem, InsertUpdateProviderItem
from .mutations.provider_item_batches import (
    DeleteProviderItemBatch,
    InsertUpdateProviderItemBatch,
)
from .mutations.quote import DeleteQuote, InsertUpdateQuote
from .mutations.quote_item import DeleteQuoteItem, InsertUpdateQuoteItem
from .mutations.request import DeleteRequest, InsertUpdateRequest
from .mutations.segment import DeleteSegment, InsertUpdateSegment
from .mutations.segment_contact import DeleteSegmentContact, InsertUpdateSegmentContact
from .mutations.discount_prompt import InsertUpdateDiscountPrompt, DeleteDiscountPrompt
from .queries.cancellation_policy import (
    resolve_cancellation_policy,
    resolve_cancellation_policy_list,
)
from .queries.bundle import resolve_bundle, resolve_bundle_list
from .queries.bundle_component import (
    resolve_bundle_component,
    resolve_bundle_component_list,
)
from .mutations.availability import (
    AcquireAvailabilityHold,
    ConfirmAvailabilityHold,
    ExpireAvailabilityHold,
    ReleaseAvailabilityHold,
)
from .queries.availability import resolve_check_availability
from .queries.discount_prompt import (
    resolve_discount_prompt,
    resolve_discount_prompt_list,
    resolve_discount_prompts,
)
from .queries.file import resolve_file, resolve_file_list
from .queries.catalog_inquiry import resolve_inquire_catalog
from .queries.fx_rate import resolve_fx_rate, resolve_fx_rate_list
from .queries.item_catalog_ref import (
    find_item_catalog_refs,
    resolve_item_catalog_ref,
    resolve_item_catalog_ref_list,
)
from .queries.installment import resolve_installment, resolve_installment_list
from .queries.item import resolve_item, resolve_item_list
from .queries.item_price_tier import (
    resolve_item_price_tier,
    resolve_item_price_tier_list,
    resolve_item_price_tiers,
)
from .queries.provider_item import resolve_provider_item, resolve_provider_item_list
from .queries.provider_item_batches import (
    resolve_provider_item_batch,
    resolve_provider_item_batch_list,
)
from .queries.quote import resolve_quote, resolve_quote_list
from .queries.quote_item import resolve_quote_item, resolve_quote_item_list
from .queries.request import resolve_request, resolve_request_list
from .queries.segment import resolve_segment, resolve_segment_list
from .queries.segment_contact import (
    resolve_segment_contact,
    resolve_segment_contact_list,
)
from .types.cancellation_policy import (
    CancellationPolicyListType,
    CancellationPolicyType,
)
from .types.bundle import BundleListType, BundleType
from .types.bundle_component import BundleComponentListType, BundleComponentType
from .types.availability import AvailabilityResultType
from .types.catalog_inquiry import CatalogInquiryResultType
from .types.discount_prompt import DiscountPromptListType, DiscountPromptType
from .types.fx_rate import FxRateListType, FxRateType
from .types.item_catalog_ref import ItemCatalogRefListType, ItemCatalogRefType
from .types.file import FileListType, FileType
from .types.installment import InstallmentListType, InstallmentType
from .types.item import ItemListType, ItemType
from .types.item_price_tier import ItemPriceTierListType, ItemPriceTierType
from .types.provider_item import ProviderItemListType, ProviderItemType
from .types.provider_item_batches import (
    ProviderItemBatchListType,
    ProviderItemBatchType,
)
from .types.quote import QuoteListType, QuoteType
from .types.quote_item import QuoteItemListType, QuoteItemType
from .types.request import RequestListType, RequestType
from .types.segment import SegmentListType, SegmentType
from .types.segment_contact import SegmentContactListType, SegmentContactType


def type_class():
    return [
        AvailabilityResultType,
        BundleType,
        BundleListType,
        BundleComponentType,
        BundleComponentListType,
        CancellationPolicyType,
        CancellationPolicyListType,
        CatalogInquiryResultType,
        DiscountPromptType,
        DiscountPromptListType,
        FxRateType,
        FxRateListType,
        ItemCatalogRefType,
        ItemCatalogRefListType,
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
        ProviderItemBatchType,
        ProviderItemBatchListType,
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
        item_uuid=String(required=False),
        item_external_id=String(required=False),
    )

    item_list = Field(
        ItemListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        item_type=String(required=False),
        item_name=String(required=False),
        item_description=String(required=False),
        pricing_mode=String(required=False),
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
        provider_corp_external_id=String(required=False),
        segment_name=String(required=False),
        segment_description=String(required=False),
    )

    segment_contact = Field(
        SegmentContactType,
        segment_uuid=String(required=False),
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
        provider_item_uuid=String(required=False),
        provider_item_external_id=String(required=False),
    )

    provider_item_list = Field(
        ProviderItemListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        item_uuid=String(required=False),
        provider_corp_external_id=String(required=False),
        provider_item_external_id=String(required=False),
        min_base_price_per_uom=Float(required=False),
        max_base_price_per_uom=Float(required=False),
    )

    provider_item_batch = Field(
        ProviderItemBatchType,
        provider_item_uuid=String(required=True),
        batch_no=String(required=True),
    )

    provider_item_batch_list = Field(
        ProviderItemBatchListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        provider_item_uuid=String(required=False),
        item_uuid=String(required=False),
        expired_at_gt=DateTime(required=False),
        expired_at_lt=DateTime(required=False),
        produced_at_gt=DateTime(required=False),
        produced_at_lt=DateTime(required=False),
        min_cost_per_uom=Float(required=False),
        max_cost_per_uom=Float(required=False),
        min_total_cost_per_uom=Float(required=False),
        max_total_cost_per_uom=Float(required=False),
        slow_move_item=Boolean(required=False),
        in_stock=Boolean(required=False),
        service_start_at_gt=DateTime(required=False),
        service_start_at_lt=DateTime(required=False),
        service_end_at_gt=DateTime(required=False),
        service_end_at_lt=DateTime(required=False),
        service_window_start=DateTime(required=False),
        service_window_end=DateTime(required=False),
        updated_at_gt=DateTime(required=False),
        updated_at_lt=DateTime(required=False),
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
        quantity_value=Float(required=False),
        min_price=Float(required=False),
        max_price=Float(required=False),
        pax_type=String(required=False),
        status=String(required=False),
    )

    item_price_tiers = List(
        ItemPriceTierType,
        email=String(required=True),
        quote_items=List(JSONCamelCase, required=False),
    )

    discount_prompt = Field(
        DiscountPromptType,
        discount_prompt_uuid=String(required=True),
    )

    discount_prompt_list = Field(
        DiscountPromptListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        scope=String(required=False),
        tags=List(String, required=False),
        status=String(required=False),
        updated_at_gt=DateTime(required=False),
        updated_at_lt=DateTime(required=False),
    )

    discount_prompts = List(
        DiscountPromptType,
        email=String(required=True),
        quote_items=List(JSONCamelCase, required=False),
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
        bundle_uuid=String(required=False),
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
        provider_corp_external_id=String(required=False),
        contact_uuid=String(required=False),
        shipping_methods=List(String, required=False),
        min_shipping_amount=Float(required=False),
        max_shipping_amount=Float(required=False),
        min_total_quote_amount=Float(required=False),
        max_total_quote_amount=Float(required=False),
        min_total_quote_discount=Float(required=False),
        max_total_quote_discount=Float(required=False),
        min_final_total_quote_amount=Float(required=False),
        max_final_total_quote_amount=Float(required=False),
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
        bundle_uuid=String(required=False),
        bundle_component_uuid=String(required=False),
        min_price_per_uom=Float(required=False),
        max_price_per_uom=Float(required=False),
        min_qty=Float(required=False),
        max_qty=Float(required=False),
        min_subtotal=Float(required=False),
        max_subtotal=Float(required=False),
        min_subtotal_discount=Float(required=False),
        max_subtotal_discount=Float(required=False),
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

    fx_rate = Field(
        FxRateType,
        fx_rate_uuid=String(required=True),
    )

    fx_rate_list = Field(
        FxRateListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        source_currency=String(required=False),
        target_currency=String(required=False),
        status=String(required=False),
    )

    cancellation_policy = Field(
        CancellationPolicyType,
        policy_uuid=String(required=True),
    )

    cancellation_policy_list = Field(
        CancellationPolicyListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        provider_item_uuid=String(required=False),
        status=String(required=False),
    )

    bundle = Field(
        BundleType,
        bundle_uuid=String(required=True),
    )

    bundle_list = Field(
        BundleListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        bundle_code=String(required=False),
        bundle_type=String(required=False),
        status=String(required=False),
    )

    bundle_component = Field(
        BundleComponentType,
        bundle_component_uuid=String(required=True),
    )

    bundle_component_list = Field(
        BundleComponentListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        bundle_uuid=String(required=False),
        item_uuid=String(required=False),
        provider_item_uuid=String(required=False),
        component_role=String(required=False),
        status=String(required=False),
    )

    item_catalog_ref = Field(
        ItemCatalogRefType,
        catalog_ref_uuid=String(required=True),
    )

    item_catalog_ref_list = Field(
        ItemCatalogRefListType,
        page_number=Int(required=False),
        limit=Int(required=False),
        namespace=String(required=False),
        item_uuid=String(required=False),
        status=String(required=False),
    )

    item_catalog_refs = List(
        ItemCatalogRefType,
        namespace=String(required=False),
        node_ids=List(String, required=True),
        status=String(required=False),
    )

    inquire_catalog = Field(
        CatalogInquiryResultType,
        namespace=String(required=False),
        node_id=String(required=False),
        query=JSONCamelCase(required=False),
    )

    check_availability = Field(
        AvailabilityResultType,
        provider_item_uuid=String(required=True),
        batch_no=String(required=False),
        service_start_at=DateTime(required=True),
        service_end_at=DateTime(required=True),
        pax_breakdown=JSONCamelCase(required=False),
        qty=Float(required=False),
    )

    def resolve_ping(self, info: ResolveInfo) -> str:
        return f"Hello at {time.strftime('%X')}!!"

    def resolve_item(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ItemType | None:
        return resolve_item(info, **kwargs)

    def resolve_item_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ItemListType:
        return resolve_item_list(info, **kwargs)

    def resolve_segment(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> SegmentType | None:
        return resolve_segment(info, **kwargs)

    def resolve_segment_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> SegmentListType:
        return resolve_segment_list(info, **kwargs)

    def resolve_segment_contact(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> SegmentContactType | None:
        return resolve_segment_contact(info, **kwargs)

    def resolve_segment_contact_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> SegmentContactListType:
        return resolve_segment_contact_list(info, **kwargs)

    def resolve_provider_item(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ProviderItemType | None:
        return resolve_provider_item(info, **kwargs)

    def resolve_provider_item_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ProviderItemListType:
        return resolve_provider_item_list(info, **kwargs)

    def resolve_provider_item_batch(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ProviderItemBatchType | None:
        return resolve_provider_item_batch(info, **kwargs)

    def resolve_provider_item_batch_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ProviderItemBatchListType:
        return resolve_provider_item_batch_list(info, **kwargs)

    def resolve_item_price_tier(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ItemPriceTierType | None:
        return resolve_item_price_tier(info, **kwargs)

    def resolve_item_price_tier_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ItemPriceTierListType:
        return resolve_item_price_tier_list(info, **kwargs)

    def resolve_item_price_tiers(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> List_Type[ItemPriceTierType]:
        return resolve_item_price_tiers(info, **kwargs)

    def resolve_discount_prompt(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> DiscountPromptType | None:
        return resolve_discount_prompt(info, **kwargs)

    def resolve_discount_prompt_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> DiscountPromptListType:
        return resolve_discount_prompt_list(info, **kwargs)

    def resolve_discount_prompts(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> List_Type[DiscountPromptType]:
        return resolve_discount_prompts(info, **kwargs)

    def resolve_request(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> RequestType | None:
        return resolve_request(info, **kwargs)

    def resolve_request_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> RequestListType:
        return resolve_request_list(info, **kwargs)

    def resolve_quote(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> QuoteType | None:
        return resolve_quote(info, **kwargs)

    def resolve_quote_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> QuoteListType:
        return resolve_quote_list(info, **kwargs)

    def resolve_quote_item(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> QuoteItemType | None:
        return resolve_quote_item(info, **kwargs)

    def resolve_quote_item_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> QuoteItemListType:
        return resolve_quote_item_list(info, **kwargs)

    def resolve_installment(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> InstallmentType | None:
        return resolve_installment(info, **kwargs)

    def resolve_installment_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> InstallmentListType:
        return resolve_installment_list(info, **kwargs)

    def resolve_file(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> FileType | None:
        return resolve_file(info, **kwargs)

    def resolve_file_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> FileListType:
        return resolve_file_list(info, **kwargs)

    def resolve_fx_rate(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> FxRateType | None:
        return resolve_fx_rate(info, **kwargs)

    def resolve_fx_rate_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> FxRateListType:
        return resolve_fx_rate_list(info, **kwargs)

    def resolve_cancellation_policy(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> CancellationPolicyType | None:
        return resolve_cancellation_policy(info, **kwargs)

    def resolve_cancellation_policy_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> CancellationPolicyListType:
        return resolve_cancellation_policy_list(info, **kwargs)

    def resolve_bundle(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> BundleType | None:
        return resolve_bundle(info, **kwargs)

    def resolve_bundle_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> BundleListType:
        return resolve_bundle_list(info, **kwargs)

    def resolve_bundle_component(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> BundleComponentType | None:
        return resolve_bundle_component(info, **kwargs)

    def resolve_bundle_component_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> BundleComponentListType:
        return resolve_bundle_component_list(info, **kwargs)

    def resolve_item_catalog_ref(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ItemCatalogRefType | None:
        return resolve_item_catalog_ref(info, **kwargs)

    def resolve_item_catalog_ref_list(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> ItemCatalogRefListType:
        return resolve_item_catalog_ref_list(info, **kwargs)

    def resolve_item_catalog_refs(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> List_Type[ItemCatalogRefType]:
        return find_item_catalog_refs(info, **kwargs)

    def resolve_inquire_catalog(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> CatalogInquiryResultType:
        return resolve_inquire_catalog(info, **kwargs)

    def resolve_check_availability(
        self, info: ResolveInfo, **kwargs: Dict[str, Any]
    ) -> AvailabilityResultType:
        return resolve_check_availability(info, **kwargs)


class Mutations(ObjectType):
    acquire_availability_hold = AcquireAvailabilityHold.Field()
    release_availability_hold = ReleaseAvailabilityHold.Field()
    confirm_availability_hold = ConfirmAvailabilityHold.Field()
    expire_availability_hold = ExpireAvailabilityHold.Field()
    insert_update_cancellation_policy = InsertUpdateCancellationPolicy.Field()
    delete_cancellation_policy = DeleteCancellationPolicy.Field()
    insert_update_bundle = InsertUpdateBundle.Field()
    delete_bundle = DeleteBundle.Field()
    insert_update_bundle_component = InsertUpdateBundleComponent.Field()
    delete_bundle_component = DeleteBundleComponent.Field()
    insert_update_item = InsertUpdateItem.Field()
    delete_item = DeleteItem.Field()
    insert_update_segment = InsertUpdateSegment.Field()
    delete_segment = DeleteSegment.Field()
    insert_update_segment_contact = InsertUpdateSegmentContact.Field()
    delete_segment_contact = DeleteSegmentContact.Field()
    insert_update_provider_item = InsertUpdateProviderItem.Field()
    delete_provider_item = DeleteProviderItem.Field()
    insert_update_provider_item_batch = InsertUpdateProviderItemBatch.Field()
    delete_provider_item_batch = DeleteProviderItemBatch.Field()
    insert_update_item_price_tier = InsertUpdateItemPriceTier.Field()
    delete_item_price_tier = DeleteItemPriceTier.Field()
    insert_update_discount_prompt = InsertUpdateDiscountPrompt.Field()
    delete_discount_prompt = DeleteDiscountPrompt.Field()
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
    insert_update_fx_rate = InsertUpdateFxRate.Field()
    delete_fx_rate = DeleteFxRate.Field()
    insert_update_item_catalog_ref = InsertUpdateItemCatalogRef.Field()
    delete_item_catalog_ref = DeleteItemCatalogRef.Field()
