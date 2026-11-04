from pydantic import BaseModel, EmailStr, Field


class BaseSeller(BaseModel):
    name: str = Field(examples=["Cairo Crafts"])
    email: EmailStr = Field(examples=["seller@example.com"])
    address: str | None = Field(default=None, examples=["12 Tahrir St, Cairo"])
    zip_code: int | None = Field(default=None, examples=[11001])


class SellerRead(BaseSeller):
    pass

class SellerCreate(BaseSeller):
    # Zip code is the starting location of the seller's shipments
    zip_code: int = Field(
        description="Where the seller's shipments start", examples=[11001]
    )
    password: str = Field(examples=["a-strong-password"])
