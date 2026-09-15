from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.caching import cached_json, invalidate_cache
from app.core.deps import get_current_user, require_role
from app.core.errors import ConflictError, NotFoundError
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.types import UserRoleName
from app.models.user import AppUser
from app.models.vendor import Vendor
from app.schemas.vendor import VendorCreate, VendorResponse

router = APIRouter(prefix="/api/v1/vendors", tags=["vendors"])

_CAN_WRITE = require_role(UserRoleName.erp_clerk, UserRoleName.system_administrator)


@router.get("", response_model=list[VendorResponse] | None)
async def list_vendors(
    request: Request, response: Response,
    db: AsyncSession = Depends(get_db), _: AppUser = Depends(get_current_user),
    limit: int = 50, cursor: uuid.UUID | None = None,
) -> list[VendorResponse] | None:
    async def _compute():
        stmt = select(Vendor).order_by(Vendor.id).limit(min(limit, 200))
        if cursor is not None:
            stmt = stmt.where(Vendor.id > cursor)
        vendors = (await db.scalars(stmt)).all()
        return [VendorResponse.model_validate(v).model_dump(mode="json") for v in vendors]

    # Cache key includes every parameter that changes the response — a
    # stale/wrong cache hit is worse than no cache at all.
    cache_key = f"vendors:list:limit={limit}:cursor={cursor}"
    result = await cached_json(request, response, cache_key=cache_key, ttl=30, compute=_compute)
    return result  # None on a 304 — FastAPI sends the empty body correctly


@router.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor(
    vendor_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: AppUser = Depends(get_current_user),
) -> VendorResponse:
    vendor = await db.get(Vendor, vendor_id)
    if vendor is None:
        raise NotFoundError(f"vendor {vendor_id} not found")
    return VendorResponse.model_validate(vendor)


@router.post("", response_model=VendorResponse, status_code=201)
async def create_vendor(
    payload: VendorCreate, db: AsyncSession = Depends(get_db), actor: AppUser = Depends(_CAN_WRITE),
) -> VendorResponse:
    vendor = Vendor(id=uuid.uuid4(), **payload.model_dump())
    db.add(vendor)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            f"vendor_code {payload.vendor_code!r} already exists", error_code="duplicate_vendor_code",
        ) from exc

    db.add(AuditLog(actor_user_id=actor.id, action="vendor.create", entity_type="vendor",
                     entity_id=vendor.id, detail={"vendor_code": payload.vendor_code}))
    await db.commit()
    await db.refresh(vendor)
    await invalidate_cache("vendors:list:*")
    return VendorResponse.model_validate(vendor)
