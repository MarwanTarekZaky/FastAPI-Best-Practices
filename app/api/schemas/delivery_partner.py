from pydantic import BaseModel, EmailStr, Field


class BaseDeliveryPartner(BaseModel):
    name: str = Field(examples=["Speedy Couriers"])
    email: EmailStr = Field(examples=["partner@example.com"])
    serviceable_zip_codes: list[int] = Field(
        description="Zip codes this partner delivers to", examples=[[11001, 11002]]
    )
    max_handling_capacity: int = Field(
        description="Most shipments the partner handles at once", examples=[10]
    )

class DeliveryPartnerRead(BaseDeliveryPartner):
    pass

class DeliveryPartnerUpdate(BaseModel):
    serviceable_zip_codes: list[int] | None = Field(
        default=None, examples=[[11001, 11002, 11003]]
    )
    max_handling_capacity: int | None = Field(default=None, examples=[15])


class DeliveryPartnerCreate(BaseDeliveryPartner):
    password: str = Field(examples=["a-strong-password"])
