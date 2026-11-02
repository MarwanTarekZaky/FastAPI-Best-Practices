import logging

from kombu.exceptions import OperationalError  # type: ignore[import-untyped]

from app.worker import tasks

logger = logging.getLogger(__name__)


class NotificationService:
    def _enqueue(self, task, **kwargs):
        try:
            task.delay(**kwargs)
        except OperationalError:
            # The shipment is already saved, so don't fail the request because of RabbitMQ
            logger.error("Could not queue %s, is RabbitMQ running?", task.name)

    async def send_email_with_template(
        self,
        recipients: list[str],
        subject: str,
        context: dict,
        template_name: str,
    ):
        self._enqueue(
            tasks.send_email_with_template,
            recipients=recipients,
            subject=subject,
            context=context,
            template_name=template_name,
        )

    async def send_verification_code(
        self,
        shipment_id: str,
        email: str,
        phone: str | None,
    ):
        self._enqueue(
            tasks.send_verification_code,
            shipment_id=shipment_id,
            email=email,
            phone=phone,
        )
