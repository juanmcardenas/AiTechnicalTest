from fastapi import APIRouter, BackgroundTasks, Depends
from app.application.services.message_processor import MessageProcessingService
from app.infrastructure.container.container import get_message_processor
from app.infrastructure.schemas.telegram_schema import TelegramUpdate

router = APIRouter()


@router.post("/webhook/telegram")
async def telegram_webhook(
    update: TelegramUpdate,
    background_tasks: BackgroundTasks,
    processor: MessageProcessingService = Depends(get_message_processor),
):
    background_tasks.add_task(processor.receive_message, update)
    return {"ok": True}
