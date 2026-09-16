"""
Checkpointer 工厂 — 按 .env 的 CHECKPOINT_BACKEND 切换

默认 SqliteSaver（零服务端 + 跨重启 + LangGraph 官方契约）
生产可一行切换 PostgresSaver（ACID + 行级锁并发）
"""
import os
from contextlib import asynccontextmanager
from app.config import settings
from app.logger import logger


def _ensure_sqlite_dir():
    os.makedirs(settings.CHECKPOINT_SQLITE_DIR, exist_ok=True)


@asynccontextmanager
async def get_checkpointer_async():
    """获取异步 Checkpointer（默认 SqliteSaver）。"""
    backend = settings.CHECKPOINT_BACKEND.lower()

    if backend == "sqlite":
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        _ensure_sqlite_dir()
        async with AsyncSqliteSaver.from_conn_string(settings.CHECKPOINT_SQLITE_PATH) as saver:
            logger.info(f"Checkpointer: SqliteSaver ({settings.CHECKPOINT_SQLITE_PATH})")
            yield saver

    elif backend == "postgres":
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool
        pool = AsyncConnectionPool(conninfo=settings.CHECKPOINT_POSTGRES_URI)
        try:
            async with AsyncPostgresSaver(pool) as saver:
                await saver.setup()
                logger.info("Checkpointer: PostgresSaver")
                yield saver
        finally:
            await pool.close()

    elif backend == "redis":
        from langgraph.checkpoint.redis.aio import AsyncRedisSaver
        from redis.asyncio import Redis
        redis = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, decode_responses=True)
        try:
            saver = AsyncRedisSaver(redis)
            logger.info("Checkpointer: RedisSaver")
            yield saver
        finally:
            await redis.aclose()

    else:
        from langgraph.checkpoint.memory import MemorySaver
        logger.warning("Checkpointer: MemorySaver（不跨重启，仅调试用）")
        yield MemorySaver()


def get_checkpointer_sync():
    """获取同步 Checkpointer（用于测试等同步场景）。"""
    backend = settings.CHECKPOINT_BACKEND.lower()

    if backend == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver
        _ensure_sqlite_dir()
        return SqliteSaver.from_conn_string(settings.CHECKPOINT_SQLITE_PATH)
    else:
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
