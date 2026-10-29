from datetime import timedelta

from redis.asyncio import Redis

from app.config import db_settings

_token_blacklist = Redis(
    host=db_settings.REDIS_HOST,
    port=db_settings.REDIS_PORT,
    db=0
)


async def add_jti_to_blacklist(jti: str):
    await _token_blacklist.set(f"blacklist:{jti}", "blacklisted", ex=timedelta(days=7))
    

async def is_jti_blacklisted(jti: str) -> bool:
    return bool(await _token_blacklist.exists(f"blacklist:{jti}"))
