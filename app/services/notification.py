import logging

from fastapi import BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import EmailStr
from twilio.base.exceptions import TwilioException  # type: ignore[import-untyped]
from twilio.rest import Client  # type: ignore[import-untyped]

from app.config import notification_settings, twilio_settings
from app.utils import TEMPLATE_DIR

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, tasks: BackgroundTasks):
        self.tasks = tasks
        self.fastmail = FastMail(
            ConnectionConfig(
                **notification_settings.model_dump(),
                TEMPLATE_FOLDER=TEMPLATE_DIR,
            )
        )
        
        self.twilio = Client(
            twilio_settings.TWILIO_ACCOUNT_SID,
            twilio_settings.TWILIO_AUTH_TOKEN,
        )

    async def send_email(
        self,
        recipients: list[EmailStr],
        subject: str,
        body: str,
    ):
        self.tasks.add_task(
            self.fastmail.send_message,
            message=MessageSchema(
                recipients=recipients,  # type: ignore[arg-type]
                subject=subject,
                body=body,
                subtype=MessageType.plain,
            )
        )

    async def send_email_with_template(
        self,
        recipients: list[EmailStr],
        subject: str,
        context: dict,
        template_name: str,
    ):
        self.tasks.add_task(
            self.fastmail.send_message,
            message=MessageSchema(
                recipients=recipients,  # type: ignore[arg-type]
                subject=subject,
                template_body=context,
                subtype=MessageType.html,
            ),
            template_name=template_name,
        )
    
    async def send_verification_sms(self, phone: str, email: str, code: str):
        self.tasks.add_task(self._send_sms_or_email, phone, email, code)

    async def _send_sms_or_email(self, phone: str, email: str, code: str):
        body = f"Your FastShip delivery code is {code}. Share it only with the delivery partner"
        
        try:
            # Twilio's client is blocking, so it runs in a separate thread
            await run_in_threadpool(
                self.twilio.messages.create,
                to=phone,
                from_=twilio_settings.TWILIO_NUMBER,
                body=body,
            )
        except (TwilioException, OSError) as error:
            # Never log the code. The clients still needs it, so email it instead
            logger.warning("SMS failed, emailing the code: %s", error)
            await self.fastmail.send_message(
                MessageSchema(
                    recipients=[email],  # type: ignore[list-item]
                    subject="Your FastShip delivery code",
                    body=body,
                    subtype=MessageType.plain
                )
            )
            