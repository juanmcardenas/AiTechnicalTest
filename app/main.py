from contextlib import AsyncExitStack, asynccontextmanager
from fastapi import FastAPI
from app.infrastructure.database.engine import engine, checkpointer_context
from app.infrastructure.events.telegram_adapter import TelegramAdapter
from app.infrastructure.handlers.webhook_handler import router as webhook_router
from app.infrastructure.handlers.health_handler import router as health_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        checkpointer = await stack.enter_async_context(checkpointer_context())
        app.state.checkpointer = checkpointer

        telegram = TelegramAdapter()
        await telegram.set_webhook(url=f"{settings.base_url}/webhook/telegram")

        yield

        await engine.dispose()


app = FastAPI(title="Car Dealership Bot", version="2.0.0", lifespan=lifespan)
app.include_router(webhook_router)
app.include_router(health_router)
