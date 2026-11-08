from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.database.redis import add_jti_to_blacklist

from ..dependencies import (
    SellerDep,
    SellerServiceDep,
    ShipmentServiceDep,
    get_seller_access_token,
)
from ..docs import errors
from ..schemas.common import Message, Token
from ..schemas.seller import SellerCreate, SellerRead
from ..schemas.shipment import ShipmentRead

router = APIRouter(prefix="/seller", tags=["Seller"])


@router.post(
    "/signup",
    response_model=SellerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a seller",
    responses=errors(409),
)
async def register_seller(seller: SellerCreate, service: SellerServiceDep):
    """The password is stored hashed and is never returned."""
    return await service.add(seller)


@router.post(
    "/token",
    response_model=Token,
    summary="Log in",
    responses=errors(401),
)
async def login_seller(
    request_form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: SellerServiceDep,
):
    """Send the email as `username`. The token expires after a while."""
    token = await service.token(request_form.username, request_form.password)
    return Token(access_token=token)


@router.get(
    "/me",
    response_model=SellerRead,
    summary="The logged in seller",
    responses=errors(401),
)
async def get_seller_profile(seller: SellerDep):
    """The frontend uses it to show who is logged in."""
    return seller


@router.get(
    "/shipments",
    response_model=list[ShipmentRead],
    summary="My shipments",
    responses=errors(401),
)
async def get_seller_shipments(seller: SellerDep, service: ShipmentServiceDep):
    """Every shipment the logged in seller created, newest first."""
    return await service.get_by_seller(seller)


@router.get(
    "/logout",
    response_model=Message,
    summary="Log out",
    responses=errors(401),
)
async def logout_seller(token_data: Annotated[dict, Depends(get_seller_access_token)]):
    """The token stops working right away."""
    await add_jti_to_blacklist(token_data["jti"])

    return {"detail": "Successfully logged out"}
