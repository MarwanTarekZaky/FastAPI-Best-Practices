from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.exceptions import InvalidInput
from app.database.redis import add_jti_to_blacklist

from ..dependencies import (
    DeliveryPartnerDep,
    DeliveryPartnerServiceDep,
    get_partner_access_token,
)
from ..docs import errors
from ..schemas.common import Message, Token
from ..schemas.delivery_partner import (
    DeliveryPartnerCreate,
    DeliveryPartnerRead,
    DeliveryPartnerUpdate,
)

router = APIRouter(prefix="/partner", tags=["Delivery Partner"])


@router.post(
    "/signup",
    response_model=DeliveryPartnerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a delivery partner",
    responses=errors(409),
)
async def register_delivery_partner(
    delivery_partner: DeliveryPartnerCreate, service: DeliveryPartnerServiceDep
):
    """The password is stored hashed and is never returned."""
    return await service.add(delivery_partner)


@router.post(
    "/token",
    response_model=Token,
    summary="Log in",
    responses=errors(401),
)
async def login_delivery_partner(
    request_form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: DeliveryPartnerServiceDep,
):
    """Send the email as `username`. The token expires after a while."""
    token = await service.token(request_form.username, request_form.password)
    return Token(access_token=token)


@router.patch(
    "/",
    response_model=DeliveryPartnerRead,
    summary="Update the logged in partner",
    responses=errors(400, 401),
)
async def update_delivery_partner(
    partner_update: DeliveryPartnerUpdate,
    partner: DeliveryPartnerDep,
    service: DeliveryPartnerServiceDep,
):
    """Send only the fields that changed."""
    update = partner_update.model_dump(exclude_none=True)

    if not update:
        raise InvalidInput("No data provided to update")

    return await service.update(
        partner.sqlmodel_update(update),
    )


@router.get(
    "/logout",
    response_model=Message,
    summary="Log out",
    responses=errors(401),
)
async def logout_delivery_partner(
    token_data: Annotated[dict, Depends(get_partner_access_token)],
):
    """The token stops working right away."""
    await add_jti_to_blacklist(token_data["jti"])

    return {"detail": "Successfully logged out"}
