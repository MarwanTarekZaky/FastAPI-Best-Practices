import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import jwt
from fastapi import HTTPException, status

from app.config import security_settings

APP_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = APP_DIR / "templates"


def generate_access_token(data: dict, expiry: timedelta = timedelta(days=7)) -> str:
    return jwt.encode(
        payload={
            **data,
            "jti": str(uuid4()),
            "exp": datetime.now(UTC) + expiry
        },
        algorithm=security_settings.JWT_ALGORITHM,
        key=security_settings.JWT_SECRET,
    )


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            jwt=token,
            key=security_settings.JWT_SECRET,
            algorithms=[security_settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired!",
        )
    except jwt.PyJWTError:
        return None


def generate_verification_code() -> str:
    # secrets is made for security, random is predicatble
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_code(shipment_id: UUID | str, code: str) -> str:
    # The secret makes it impossible to try all 1,000,000 codes aganist a leaked hash
    return hmac.new(
        security_settings.VERIFICATION_CODE_SECRET.encode(),
        f"{shipment_id}:{code}".encode(),
        hashlib.sha256,
    ).hexdigest()
    

def is_valid_verification_code(shipment_id: UUID, code: str, stored_hash: str) -> bool:
    # compare_digest takes the same time whenever the values differ
    return hmac.compare_digest(hash_verification_code(shipment_id, code), stored_hash)