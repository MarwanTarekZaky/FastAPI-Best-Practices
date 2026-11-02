import asyncio
import logging
from datetime import UTC, datetime

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from fastapi_mail.errors import ConnectionErrors
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import col
from twilio.base.exceptions import TwilioException  # type: ignore[import-untyped]
from twilio.http.http_client import TwilioHttpClient  # type: ignore[import-untyped]
from twilio.rest import Client  # type: ignore[import-untyped]

from app.config import db_settings, notification_settings, twilio_settings
from app.database.models import Shipment, ShipmentStatus
from app.database.redis import save_verification_code
from app.utils import TEMPLATE_DIR, generate_verification_code, hash_verification_code
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

fastmail = FastMail(
    ConnectionConfig(
        **notification_settings.model_dump(),
        TEMPLATE_FOLDER=TEMPLATE_DIR,
    )
)
twilio_client = Client(
    twilio_settings.TWILIO_ACCOUNT_SID,
    twilio_settings.TWILIO_AUTH_TOKEN,
    # A hanging request would block a worker thread forever without this
    http_client=TwilioHttpClient(timeout=15),
)

# Retry when the mail server is unreachable: about 1s, 2s, 4s... with random jitter
EMAIL_RETRY_OPTIONS = {
    "autoretry_for": (ConnectionErrors,),
    "retry_backoff": True,
    "retry_jitter": True,
    "max_retries": 5,
}


def _send_template_email(
    recipients: list[str],
    subject: str,
    context: dict,
    template_name: str,
):
    # fastapi-mail is async and tasks are not, so asyncio.run bridges them
    asyncio.run(
        fastmail.send_message(
            MessageSchema(
                recipients=recipients,  # type: ignore[arg-type]
                subject=subject,
                template_body=context,
                subtype=MessageType.html,
            ),
            template_name=template_name,
        )
    )


@celery_app.task(**EMAIL_RETRY_OPTIONS)
def send_email(recipients: list[str], subject: str, body: str):
    asyncio.run(
        fastmail.send_message(
            MessageSchema(
                recipients=recipients,  # type: ignore[arg-type]
                subject=subject,
                body=body,
                subtype=MessageType.plain,
            )
        )
    )


@celery_app.task(**EMAIL_RETRY_OPTIONS)
def send_email_with_template(
    recipients: list[str],
    subject: str,
    context: dict,
    template_name: str,
):
    _send_template_email(recipients, subject, context, template_name)


@celery_app.task(bind=True, **EMAIL_RETRY_OPTIONS)
def send_verification_code(self, shipment_id: str, email: str, phone: str | None = None):
    # The code is created here so it never passes through RabbitMQ or Flower.
    # Each retry makes a new code and replaces the old hash, so only the
    # code that actually reached the client works
    code = generate_verification_code()
    save_verification_code(shipment_id, hash_verification_code(shipment_id, code))
    
    if phone:
        try:
            twilio_client.messages.create(
                to=phone,
                from_=twilio_settings.TWILIO_NUMBER,
                body=f"Your FastShip delivery code is {code}. Share it only with the delivery partner.",
            )
            return
        except (TwilioException, OSError) as error:
            # Never log the code
            logger.warning("SMS failed: %s", error)

            # Network or Twilio outage: try again. Wrong number: use email now
            temporary = getattr(error, "status", 500) >= 500
            if temporary and self.request.retries < 3:
                raise self.retry(exc=error, countdown=2**self.request.retries)

    _send_template_email(
        [email],
        "Your Order is Arriving Soon 🛵",
        {"code": code},
        "mail_out_for_delivery.html",
    )


async def _get_overdue_shipments() -> list[dict]:
    # asyncio.run makes a new event loop, so this needs its own engine without a pool
    engine = create_async_engine(db_settings.POSTGRES_URL, poolclass=NullPool)

    try:
        async with AsyncSession(engine) as session:
            shipments = await session.scalars(
                select(Shipment).where(
                    col(Shipment.estimated_delivery) < datetime.now(UTC)
                )
            )
            return [
                {
                    "id": str(shipment.id),
                    "content": shipment.content,
                    "seller_email": shipment.seller.email,
                }
                for shipment in shipments
                # No status means an old shipment from before the timeline
                if shipment.status is not None
                and shipment.status
                not in (ShipmentStatus.delivered, ShipmentStatus.cancelled)
            ]
    finally:
        await engine.dispose()


@celery_app.task
def notify_overdue_shipments() -> int:
    overdue = asyncio.run(_get_overdue_shipments())

    # One small task per email, so one failure doesn't stop the others
    for shipment in overdue:
        send_email.delay(
            recipients=[shipment["seller_email"]],
            subject="A shipment is overdue",
            body=f"Shipment {shipment['content']} ({shipment['id']}) has passed its estimated delivery date.",
        )

    return len(overdue)
