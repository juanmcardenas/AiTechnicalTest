from fastapi import APIRouter
from sqlalchemy import text
from app.infrastructure.database.engine import AsyncSessionFactory
from app.infrastructure.schemas.health_schema import HealthResponse, DependencyStatus

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    db_status = "ok"
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    return HealthResponse(
        status="ok",
        version="2.0.0",
        dependencies=DependencyStatus(
            database=db_status,
            deepseek="ok",
            langfuse="ok",
        ),
    )
