import uuid
from app.domain.repositories.email_log_repository import IEmailLogRepository
from app.infrastructure.database.models.email_log_model import EmailLogORM
from app.infrastructure.repositories.base_repository import BaseRepository


class EmailLogRepository(BaseRepository, IEmailLogRepository):
    async def log(
        self,
        lead_id: str,
        car_id: str,
        recipient: str,
        subject: str,
        template: str,
        success: bool,
        error: str | None,
    ) -> None:
        row = EmailLogORM(
            id=uuid.uuid4(),
            lead_id=uuid.UUID(lead_id),
            car_id=uuid.UUID(car_id),
            recipient_email=recipient,
            subject=subject,
            template_used=template,
            success=success,
            error_msg=error,
        )
        self.session.add(row)
        await self.session.commit()
