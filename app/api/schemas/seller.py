from pydantic import BaseModel, EmailStr


class BaseSeller(BaseModel):
    name: str
    email: EmailStr
    address: str | None = None
    zip_code: int | None = None

class SellerRead(BaseSeller):
    pass

class SellerCreate(BaseSeller):
    # Zip code is the starting location of the seller's shipments
    zip_code: int
    password: str