from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_base_config = SettingsConfigDict(
    env_file="./.env",
    env_ignore_empty=True,
    extra="ignore",
)

class AppSettings(BaseSettings):
    # "production" turns off what is only meant for your own machine,
    # like printing every SQL query and writing logs/requests.log
    ENVIRONMENT: Literal["development", "production"] = "development"
    # Browser apps (frontends) allowed to call this API. In .env, a JSON list:
    # CORS_ORIGINS=["http://localhost:5173"]
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    LOGFIRE_TOKEN: str | None = None
    
    model_config = _base_config

class DatabaseSettings(BaseSettings):
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    
    REDIS_HOST: str
    REDIS_PORT: int

    model_config = _base_config

    @property
    def POSTGRES_URL(self):
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


class SecuritySettings(BaseSettings):

    JWT_SECRET: str
    JWT_ALGORITHM: str
    VERIFICATION_CODE_SECRET: str


    model_config = _base_config

class NotificationSettings(BaseSettings):

    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_FROM_NAME: str
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True

    model_config = _base_config


class TwilioSettings(BaseSettings):
    
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_NUMBER: str

    model_config = _base_config
    
 
class CelerySettings(BaseSettings):

    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    FLOWER_USER: str
    FLOWER_PASSWORD: str

    model_config = _base_config

   
# Values are loaded from .env, type checkers can't see that
app_settings = AppSettings()
db_settings = DatabaseSettings()  # type: ignore[call-arg]
security_settings = SecuritySettings()  # type: ignore[call-arg]
notification_settings = NotificationSettings() # type: ignore[call-arg]
twilio_settings = TwilioSettings()  # type: ignore[call-arg]
celery_settings = CelerySettings()  # type: ignore[call-arg]
