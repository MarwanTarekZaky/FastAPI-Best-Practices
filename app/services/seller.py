import jwt
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.schemas.seller import SellerCreate
from app.database.models import Seller
# from app.utils import generate_accesss_token
from app.config import security_settings

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SellerService:
    def __init__(self, session: AsyncSession):
        # Get database session to perform database operations
        self.session = session

    async def add(self, credentials: SellerCreate) -> Seller:
        seller = Seller(
            **credentials.model_dump(exclude={"password"}),
            # Hashed password
            password_hash=password_context.hash(credentials.password),
        )
        self.session.add(seller)
        await self.session.commit()
        await self.session.refresh(seller)

        return seller
    
    async def token(self, email, password) -> str:
        # Validate creds
        result = await self.session.execute(
            select(Seller).where(Seller.email == email)
        )
        
        seller = result.scalar()
        if seller is None or not password_context.verify(password,seller.password_hash):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="email or password is incorrect!"
            )
        
        token = jwt.encode(
            payload={
                "user": {
                    "name": seller.name,
                    "email": seller.email
                },
                "exp": datetime.now() + timedelta(days=1)
            },
            algorithm=security_settings.JWT_ALGORITHM,
            key=security_settings.JWT_SECRET
        )
        
        return token
        