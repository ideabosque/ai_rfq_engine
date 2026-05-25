#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Availability operations using local ProviderItemBatch data."""
from __future__ import annotations

__author__ = "bibow"

import hashlib
import uuid
from typing import Any, Optional, TypedDict

import pendulum
from graphene import ResolveInfo
from pynamodb.exceptions import DoesNotExist, TransactWriteError
from pynamodb.transactions import TransactWrite


class _RequiredAvailabilityRequest(TypedDict):
    provider_item_uuid: str


class AvailabilityRequest(_RequiredAvailabilityRequest, total=False):
    batch_no: Optional[str]
    service_start_at: Any
    service_end_at: Any
    pax_breakdown: Optional[Any]
    qty: Optional[float]
    hold_token: Optional[str]
    quote_uuid: Optional[str]
    quote_item_uuid: Optional[str]


class AvailabilityResponse(TypedDict, total=False):
    operation: str
    request: AvailabilityRequest
    available: bool
    hold_token: Optional[str]
    expires_at: Optional[str]
    fetched_at: str
    ttl_seconds: Optional[int]
    payload: Any


class AvailabilityHandlerError(Exception):
    code = "system_error"

    def __init__(self, message: str = "", *, details: Optional[dict] = None) -> None:
        super().__init__(message or self.__class__.__name__)
        self.details = details or {}


class OperationUnsupportedError(AvailabilityHandlerError):
    code = "operation_unsupported"


class UnknownHoldError(AvailabilityHandlerError):
    code = "unknown_hold"


class SystemTimeoutError(AvailabilityHandlerError):
    code = "system_timeout"


class SystemError(AvailabilityHandlerError):
    code = "system_error"


_HOLD_TTL_SECONDS = 900


def _build_request(
    provider_item_uuid: str,
    *,
    batch_no: Optional[str],
    service_start_at: Any,
    service_end_at: Any,
    pax_breakdown: Optional[Any],
    qty: Optional[float],
    hold_token: Optional[str],
) -> AvailabilityRequest:
    return {
        "provider_item_uuid": provider_item_uuid,
        "batch_no": batch_no,
        "service_start_at": service_start_at,
        "service_end_at": service_end_at,
        "pax_breakdown": pax_breakdown,
        "qty": qty,
        "hold_token": hold_token,
    }


def _parse_dt(value: Any) -> Optional[Any]:
    if value is None:
        return None
    if isinstance(value, str):
        return pendulum.parse(value)
    return value


def _generate_hold_token(provider_item_uuid: str, batch_no: Optional[str]) -> str:
    seed = f"{provider_item_uuid}:{batch_no or ''}:{uuid.uuid4()}"
    return hashlib.sha256(seed.encode()).hexdigest()[:32]


def _updated_by(info: ResolveInfo) -> str:
    return (
        info.context.get("updated_by")
        or info.context.get("username")
        or info.context.get("partition_key")
        or "availability"
    )


def _get_hold(partition_key: str, hold_token: str) -> Any:
    from ai_rfq_engine.models.availability_hold import AvailabilityHoldModel

    try:
        return AvailabilityHoldModel.get(partition_key, hold_token)
    except DoesNotExist as exc:
        raise UnknownHoldError("Unknown availability hold token") from exc


def _reserve_capacity_for_hold(
    info: ResolveInfo,
    *,
    provider_item_uuid: str,
    batch_no: str,
    qty: float,
    hold_token: str,
    service_start_at: Any,
    service_end_at: Any,
    expires_at: Any,
    quote_uuid: Optional[str] = None,
    quote_item_uuid: Optional[str] = None,
) -> Any:
    from ai_rfq_engine.models.availability_hold import AvailabilityHoldModel
    from ai_rfq_engine.models.provider_item_batches import (
        ProviderItemBatchModel,
        get_provider_item_batch,
    )

    partition_key = info.context["partition_key"]
    batch = get_provider_item_batch(provider_item_uuid, batch_no)
    if _batch_available_qty(batch) is None:
        raise ValueError(
            "require_hold requires a quantified availability_qty for local inventory"
        )
    now = pendulum.now("UTC")
    hold = AvailabilityHoldModel(
        partition_key,
        hold_token,
        provider_item_uuid=provider_item_uuid,
        batch_no=batch_no,
        quote_uuid=quote_uuid,
        quote_item_uuid=quote_item_uuid,
        qty=qty,
        service_start_at=_parse_dt(service_start_at),
        service_end_at=_parse_dt(service_end_at),
        status=AvailabilityHoldModel.HELD,
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
        updated_by=_updated_by(info),
    )
    condition = (
        (ProviderItemBatchModel.in_stock == True)  # noqa: E712
        & ProviderItemBatchModel.availability_qty.exists()
        & (ProviderItemBatchModel.availability_qty >= qty)
    )
    try:
        with TransactWrite(
            connection=ProviderItemBatchModel._get_connection().connection
        ) as transaction:
            transaction.update(
                batch,
                actions=[
                    ProviderItemBatchModel.availability_qty.add(-qty),
                    ProviderItemBatchModel.updated_at.set(now),
                ],
                condition=condition,
            )
            transaction.save(
                hold,
                condition=AvailabilityHoldModel.hold_token.does_not_exist(),
            )
    except TransactWriteError:
        return None
    return hold


def _confirm_stored_hold(info: ResolveInfo, hold: Any) -> Any:
    from ai_rfq_engine.models.availability_hold import AvailabilityHoldModel

    now = pendulum.now("UTC")
    if hold.status == AvailabilityHoldModel.CONFIRMED:
        return hold
    if hold.status in {AvailabilityHoldModel.RELEASED, AvailabilityHoldModel.EXPIRED}:
        raise UnknownHoldError(f"Availability hold is already {hold.status}")
    if hold.expires_at <= now:
        _restore_stored_hold(info, hold, AvailabilityHoldModel.EXPIRED)
        raise UnknownHoldError("Availability hold has expired")
    try:
        with TransactWrite(
            connection=AvailabilityHoldModel._get_connection().connection
        ) as transaction:
            transaction.update(
                hold,
                actions=[
                    AvailabilityHoldModel.status.set(AvailabilityHoldModel.CONFIRMED),
                    AvailabilityHoldModel.updated_at.set(now),
                    AvailabilityHoldModel.updated_by.set(_updated_by(info)),
                ],
                condition=(
                    (AvailabilityHoldModel.status == AvailabilityHoldModel.HELD)
                    & (AvailabilityHoldModel.expires_at > now)
                ),
            )
    except TransactWriteError as exc:
        current = _get_hold(hold.partition_key, hold.hold_token)
        if current.status == AvailabilityHoldModel.CONFIRMED:
            return current
        raise UnknownHoldError("Availability hold cannot be confirmed") from exc
    hold.status = AvailabilityHoldModel.CONFIRMED
    return hold


def _restore_stored_hold(info: ResolveInfo, hold: Any, status: str) -> Any:
    from ai_rfq_engine.models.availability_hold import AvailabilityHoldModel
    from ai_rfq_engine.models.provider_item_batches import (
        ProviderItemBatchModel,
        get_provider_item_batch,
    )

    if hold.status == status:
        return hold
    if hold.status in {AvailabilityHoldModel.RELEASED, AvailabilityHoldModel.EXPIRED}:
        raise UnknownHoldError(f"Availability hold is already {hold.status}")
    if hold.status == AvailabilityHoldModel.CONFIRMED:
        raise UnknownHoldError("Confirmed reservation cannot be released as a hold")
    now = pendulum.now("UTC")
    batch = get_provider_item_batch(hold.provider_item_uuid, hold.batch_no)
    try:
        with TransactWrite(
            connection=ProviderItemBatchModel._get_connection().connection
        ) as transaction:
            transaction.update(
                hold,
                actions=[
                    AvailabilityHoldModel.status.set(status),
                    AvailabilityHoldModel.updated_at.set(now),
                    AvailabilityHoldModel.updated_by.set(_updated_by(info)),
                ],
                condition=AvailabilityHoldModel.status == AvailabilityHoldModel.HELD,
            )
            transaction.update(
                batch,
                actions=[
                    ProviderItemBatchModel.availability_qty.add(float(hold.qty)),
                    ProviderItemBatchModel.updated_at.set(now),
                ],
            )
    except TransactWriteError as exc:
        current = _get_hold(hold.partition_key, hold.hold_token)
        if current.status == status:
            return current
        raise UnknownHoldError("Availability hold cannot be released") from exc
    hold.status = status
    return hold


def _find_matching_batches(
    info: ResolveInfo,
    provider_item_uuid: str,
    service_start_at: Any = None,
    service_end_at: Any = None,
    batch_no: Optional[str] = None,
) -> list:
    from ai_rfq_engine.models.provider_item_batches import resolve_provider_item_batch_list

    kwargs: dict[str, Any] = {
        "provider_item_uuid": provider_item_uuid,
    }
    if batch_no:
        kwargs["batch_no"] = batch_no
    if service_start_at and service_end_at:
        kwargs["service_window_start"] = service_start_at
        kwargs["service_window_end"] = service_end_at

    result = resolve_provider_item_batch_list(info, **kwargs)
    batches = list(result.provider_item_batch_list) if result and result.provider_item_batch_list else []
    return batches


def _batch_available_qty(batch: Any) -> Optional[float]:
    aq = getattr(batch, "availability_qty", None)
    if aq is not None:
        try:
            return float(aq)
        except (TypeError, ValueError):
            return None
    return None


def _batch_is_available(batch: Any, qty: Optional[float] = None) -> bool:
    if not getattr(batch, "in_stock", True):
        return False
    available_qty = _batch_available_qty(batch)
    if available_qty is not None and qty is not None:
        return available_qty >= float(qty)
    return True


def _validate_requested_qty(qty: Optional[float]) -> None:
    if qty is None:
        return
    try:
        requested_qty = float(qty)
    except (TypeError, ValueError):
        raise ValueError(f"qty must be numeric, got: {qty!r}")
    if requested_qty <= 0:
        raise ValueError(f"qty must be greater than 0, got: {qty}")


def _check_availability(
    info: ResolveInfo,
    *,
    provider_item_uuid: str,
    batch_no: Optional[str] = None,
    service_start_at: Any = None,
    service_end_at: Any = None,
    pax_breakdown: Optional[Any] = None,
    qty: Optional[float] = None,
    hold_token: Optional[str] = None,
    quote_uuid: Optional[str] = None,
    quote_item_uuid: Optional[str] = None,
) -> AvailabilityResponse:
    if not info.context.get("partition_key"):
        raise SystemError("partition_key is required for availability checks")
    _validate_requested_qty(qty)

    request = _build_request(
        provider_item_uuid,
        batch_no=batch_no,
        service_start_at=service_start_at,
        service_end_at=service_end_at,
        pax_breakdown=pax_breakdown,
        qty=qty,
        hold_token=None,
    )

    batches = _find_matching_batches(
        info,
        provider_item_uuid,
        service_start_at=service_start_at,
        service_end_at=service_end_at,
        batch_no=batch_no,
    )

    if not batches:
        return {
            "operation": "check",
            "request": request,
            "available": False,
            "hold_token": None,
            "expires_at": None,
            "fetched_at": pendulum.now("UTC").to_iso8601_string(),
            "ttl_seconds": None,
            "payload": {"reason": "no_matching_batches"},
        }

    available_batches = [b for b in batches if _batch_is_available(b, qty)]
    if not available_batches:
        unavailable_batches = [b for b in batches if not getattr(b, "in_stock", True)]
        reason = "all_batches_out_of_stock" if len(unavailable_batches) == len(batches) else "insufficient_availability"
        return {
            "operation": "check",
            "request": request,
            "available": False,
            "hold_token": None,
            "expires_at": None,
            "fetched_at": pendulum.now("UTC").to_iso8601_string(),
            "ttl_seconds": None,
            "payload": {"reason": reason},
        }

    slow_move = any(getattr(b, "slow_move_item", False) for b in available_batches)
    total_available = sum(
        _batch_available_qty(b) for b in available_batches
        if _batch_available_qty(b) is not None
    ) or None
    payload = {
        "reason": "available",
        "matched_batches": len(batches),
        "available_batches": len(available_batches),
        "total_available_qty": total_available,
        "slow_move": slow_move,
    }

    return {
        "operation": "check",
        "request": request,
        "available": True,
        "hold_token": None,
        "expires_at": None,
        "fetched_at": pendulum.now("UTC").to_iso8601_string(),
        "ttl_seconds": None,
        "payload": payload,
    }


def _acquire_hold(
    info: ResolveInfo,
    *,
    provider_item_uuid: str,
    batch_no: Optional[str] = None,
    service_start_at: Any = None,
    service_end_at: Any = None,
    pax_breakdown: Optional[Any] = None,
    qty: Optional[float] = None,
    quote_uuid: Optional[str] = None,
    quote_item_uuid: Optional[str] = None,
    hold_token: Optional[str] = None,
) -> AvailabilityResponse:
    if not info.context.get("partition_key"):
        raise SystemError("partition_key is required for availability holds")
    _validate_requested_qty(qty)

    start = _parse_dt(service_start_at)
    end = _parse_dt(service_end_at)
    if start is None or end is None:
        raise ValueError(
            "service_start_at and service_end_at are required for availability holds"
        )
    if end <= start:
        raise ValueError("service_end_at must be later than service_start_at")
    if qty is None:
        raise ValueError("qty is required for availability holds")

    request = _build_request(
        provider_item_uuid,
        batch_no=batch_no,
        service_start_at=service_start_at,
        service_end_at=service_end_at,
        pax_breakdown=pax_breakdown,
        qty=qty,
        hold_token=None,
    )

    batches = _find_matching_batches(
        info,
        provider_item_uuid,
        service_start_at=service_start_at,
        service_end_at=service_end_at,
        batch_no=batch_no,
    )

    if not batches:
        raise ValueError(
            f"No matching batches found for provider_item_uuid={provider_item_uuid}"
        )

    quantified_batches = [b for b in batches if _batch_available_qty(b) is not None]
    available_batches = [b for b in quantified_batches if _batch_is_available(b, qty)]
    if not available_batches:
        unavailable_batches = [b for b in batches if not getattr(b, "in_stock", True)]
        if not quantified_batches:
            reason = "unquantified_capacity"
        else:
            reason = (
                "all_batches_out_of_stock"
                if len(unavailable_batches) == len(batches)
                else "insufficient_availability"
            )
        return {
            "operation": "acquire_hold",
            "request": request,
            "available": False,
            "hold_token": None,
            "expires_at": None,
            "fetched_at": pendulum.now("UTC").to_iso8601_string(),
            "ttl_seconds": None,
            "payload": {"reason": reason},
        }

    selected_batch = available_batches[0]
    selected_batch_no = getattr(selected_batch, "batch_no", batch_no)
    if not selected_batch_no:
        raise ValueError("A matching batch_no is required for availability holds")
    request["batch_no"] = selected_batch_no
    hold_token = _generate_hold_token(provider_item_uuid, selected_batch_no)
    expires_at = pendulum.now("UTC").add(seconds=_HOLD_TTL_SECONDS)
    hold = _reserve_capacity_for_hold(
        info,
        provider_item_uuid=provider_item_uuid,
        batch_no=selected_batch_no,
        qty=float(qty),
        hold_token=hold_token,
        service_start_at=service_start_at,
        service_end_at=service_end_at,
        expires_at=expires_at,
        quote_uuid=quote_uuid,
        quote_item_uuid=quote_item_uuid,
    )
    if hold is None:
        return {
            "operation": "acquire_hold",
            "request": request,
            "available": False,
            "hold_token": None,
            "expires_at": None,
            "fetched_at": pendulum.now("UTC").to_iso8601_string(),
            "ttl_seconds": None,
            "payload": {"reason": "insufficient_availability"},
        }

    slow_move = any(getattr(b, "slow_move_item", False) for b in available_batches)
    total_available = sum(
        _batch_available_qty(b) for b in available_batches
        if _batch_available_qty(b) is not None
    ) or None
    payload = {
        "reason": "hold_acquired",
        "matched_batches": len(batches),
        "available_batches": len(available_batches),
        "total_available_qty": total_available,
        "slow_move": slow_move,
    }

    return {
        "operation": "acquire_hold",
        "request": request,
        "available": True,
        "hold_token": hold_token,
        "expires_at": expires_at.to_iso8601_string(),
        "fetched_at": pendulum.now("UTC").to_iso8601_string(),
        "ttl_seconds": _HOLD_TTL_SECONDS,
        "payload": payload,
    }


def _confirm_hold(
    info: ResolveInfo,
    *,
    provider_item_uuid: str,
    batch_no: Optional[str] = None,
    hold_token: Optional[str] = None,
    **_: Any,
) -> AvailabilityResponse:
    if not info.context.get("partition_key"):
        raise SystemError("partition_key is required for availability hold confirmation")

    if not hold_token:
        raise ValueError("hold_token is required for hold confirmation")

    request = _build_request(
        provider_item_uuid,
        batch_no=batch_no,
        service_start_at=None,
        service_end_at=None,
        pax_breakdown=None,
        qty=None,
        hold_token=hold_token,
    )

    hold = _get_hold(info.context["partition_key"], hold_token)
    if hold.provider_item_uuid != provider_item_uuid or (
        batch_no and hold.batch_no != batch_no
    ):
        raise UnknownHoldError("Availability hold does not match the requested batch")
    _confirm_stored_hold(info, hold)
    return {
        "operation": "confirm_hold",
        "request": request,
        "available": True,
        "hold_token": hold_token,
        "expires_at": None,
        "fetched_at": pendulum.now("UTC").to_iso8601_string(),
        "ttl_seconds": None,
        "payload": {"reason": "hold_confirmed"},
    }


def _release_hold(
    info: ResolveInfo,
    *,
    provider_item_uuid: str,
    batch_no: Optional[str] = None,
    hold_token: Optional[str] = None,
    **_: Any,
) -> AvailabilityResponse:
    if not info.context.get("partition_key"):
        raise SystemError("partition_key is required for availability hold release")

    if not hold_token:
        raise ValueError("hold_token is required for hold release")

    request = _build_request(
        provider_item_uuid,
        batch_no=batch_no,
        service_start_at=None,
        service_end_at=None,
        pax_breakdown=None,
        qty=None,
        hold_token=hold_token,
    )

    hold = _get_hold(info.context["partition_key"], hold_token)
    if hold.provider_item_uuid != provider_item_uuid or (
        batch_no and hold.batch_no != batch_no
    ):
        raise UnknownHoldError("Availability hold does not match the requested batch")
    if hold.status == "expired":
        raise UnknownHoldError("Availability hold has expired")
    _restore_stored_hold(info, hold, "released")
    return {
        "operation": "release_hold",
        "request": request,
        "available": True,
        "hold_token": hold_token,
        "expires_at": None,
        "fetched_at": pendulum.now("UTC").to_iso8601_string(),
        "ttl_seconds": None,
        "payload": {"reason": "hold_released"},
    }


def _expire_hold(
    info: ResolveInfo,
    *,
    provider_item_uuid: str,
    batch_no: Optional[str] = None,
    hold_token: Optional[str] = None,
    **_: Any,
) -> AvailabilityResponse:
    if not info.context.get("partition_key"):
        raise SystemError("partition_key is required for availability hold expiry")
    if not hold_token:
        raise ValueError("hold_token is required for hold expiry")
    hold = _get_hold(info.context["partition_key"], hold_token)
    if hold.provider_item_uuid != provider_item_uuid or (
        batch_no and hold.batch_no != batch_no
    ):
        raise UnknownHoldError("Availability hold does not match the requested batch")
    if hold.status in {"released", "confirmed"}:
        raise UnknownHoldError(f"Availability hold is already {hold.status}")
    if hold.status == "held" and hold.expires_at > pendulum.now("UTC"):
        raise UnknownHoldError("Availability hold has not expired")
    _restore_stored_hold(info, hold, "expired")
    request = _build_request(
        provider_item_uuid,
        batch_no=hold.batch_no,
        service_start_at=None,
        service_end_at=None,
        pax_breakdown=None,
        qty=None,
        hold_token=hold_token,
    )
    return {
        "operation": "expire_hold",
        "request": request,
        "available": False,
        "hold_token": hold_token,
        "expires_at": None,
        "fetched_at": pendulum.now("UTC").to_iso8601_string(),
        "ttl_seconds": None,
        "payload": {"reason": "hold_expired"},
    }


def dispatch_check(info: ResolveInfo, **kwargs: Any) -> AvailabilityResponse:
    from ..telemetry import measure_handler_duration

    with measure_handler_duration(info, operation="check", handler="availability"):
        return _check_availability(info, **kwargs)


def dispatch_acquire_hold(info: ResolveInfo, **kwargs: Any) -> AvailabilityResponse:
    from ..telemetry import measure_handler_duration

    with measure_handler_duration(info, operation="acquire_hold", handler="availability"):
        return _acquire_hold(info, **kwargs)


def dispatch_release_hold(info: ResolveInfo, **kwargs: Any) -> AvailabilityResponse:
    from ..telemetry import measure_handler_duration

    with measure_handler_duration(info, operation="release_hold", handler="availability"):
        return _release_hold(info, **kwargs)


def dispatch_confirm_hold(info: ResolveInfo, **kwargs: Any) -> AvailabilityResponse:
    from ..telemetry import measure_handler_duration

    with measure_handler_duration(info, operation="confirm_hold", handler="availability"):
        return _confirm_hold(info, **kwargs)


def dispatch_expire_hold(info: ResolveInfo, **kwargs: Any) -> AvailabilityResponse:
    from ..telemetry import measure_handler_duration

    with measure_handler_duration(info, operation="expire_hold", handler="availability"):
        return _expire_hold(info, **kwargs)
