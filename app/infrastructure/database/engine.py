from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    echo=settings.app_env == "development",
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        yield session


async def get_checkpointer() -> AsyncPostgresSaver:
    checkpointer = AsyncPostgresSaver.from_conn_string(
        settings.database_url.replace("+asyncpg", "")
    )
    await checkpointer.setup()
    return checkpointer
