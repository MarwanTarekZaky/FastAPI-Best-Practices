from datetime import timedelta
from uuid import UUID

from redis.asyncio import Redis

from app.config import db_settings

_token_blacklist = Redis(
    host=db_settings.REDIS_HOST,
    port=db_settings.REDIS_PORT,
    db=0
)

_verification = Redis(
    host=db_settings.REDIS_HOST,
    port=db_settings.REDIS_PORT,
    db=0,
    decode_responses=True,
)

VERIFICATION_CODE_TTL = timedelta(hours=24)
VERIFICATION_RESEND_COOLDOWN = timedelta(seconds=60)


async def add_jti_to_blacklist(jti: str):
    await _token_blacklist.set(f"blacklist:{jti}", "blacklisted", ex=timedelta(days=7))
    

async def is_jti_blacklisted(jti: str) -> bool:
    return bool(await _token_blacklist.exists(f"blacklist:{jti}"))


async def save_verification_code(shipment_id: UUID, code_hash: str):
    # A new code replace the old one and reset the failed attempts
    await _verification.set(
        f"verification:code:{shipment_id}", code_hash, ex=VERIFICATION_CODE_TTL
    )
    await _verification.delete(f"verification:attempts:{shipment_id}")
    
async def get_verification_code_hash(shipment_id: UUID) -> str | None:
    return await _verification.get(f"verification:code:{shipment_id}")  # type: ignore[return-value]


async def count_verification_attempt(shipment_id: UUID) -> int:
    # INCR is atomic, parallel requests can't slip past limit
    key = f"verification:attempts:{shipment_id}"
    attempts = await _verification.incr(key)
    await _verification.expire(key, VERIFICATION_CODE_TTL)
    return attempts


async def delete_verification_code(shipment_id: UUID):
    await _verification.delete(
        f"verification:code:{shipment_id}",
        f"verification:attempts:{shipment_id}"
    )
    

async def can_resend_verification_code(shipment_id: UUID) -> bool:
    # NX only sets the key if it doesn't exists, so it returns None during the cooldown
    return bool(
        await _verification.set(
            f"verification:resend:{shipment_id}",
            "1",
            nx=True,
            ex=VERIFICATION_RESEND_COOLDOWN,
        )
    )