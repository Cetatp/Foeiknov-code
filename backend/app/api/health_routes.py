"""
健康检查路由 — GET /health

逐项探测 MySQL / Milvus / LLM / Checkpointer / Redis，
返回每个组件的 ok/fail 状态，前端可据此做连接状态指示灯。
"""
from fastapi import APIRouter
from sqlalchemy import text
from pymilvus import MilvusClient

from app.config import settings
from app.schemas.api_models import HealthResponse

router = APIRouter(tags=["health"])


def _check_mysql() -> str:
    """MySQL 连通性探测。"""
    try:
        from app.database.mysql_client import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as e:
        return f"fail: {e}"


def _check_milvus() -> str:
    """Milvus 连通性探测。"""
    try:
        c = MilvusClient(uri=f"http://{settings.MILVUS_DB_PATH}", db_name=settings.MILVUS_DB_NAME)
        c.list_collections()
        return "ok"
    except Exception as e:
        return f"fail: {e}"


def _check_llm() -> str:
    """LLM API Key 是否配置（不实际调用，避免浪费 token）。"""
    if settings.DEEPSEEK_API_KEY:
        return "ok"
    return "fail: DEEPSEEK_API_KEY 未配置"


def _check_checkpointer() -> str:
    """Checkpointer 后端类型（仅检查配置，不实际创建）。"""
    backend = settings.CHECKPOINT_BACKEND.lower()
    supported = {"sqlite", "postgres", "redis", "memory"}
    if backend in supported:
        return f"ok ({backend})"
    return f"fail: unknown backend {backend}"


def _check_redis() -> str:
    """Redis 连通性探测（跳过：Redis 仅加速层，非必需）。"""
    if settings.REDIS_HOST == "127.0.0.1" and settings.REDIS_PORT == 6379:
        return "skipped (optional)"
    try:
        import redis
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, socket_connect_timeout=1)
        r.ping()
        return "ok"
    except Exception as e:
        return f"fail: {e}"


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    全链路健康检查。

    返回每个组件的 ok/fail 状态，前端可据此显示连接状态指示灯。
    """
    return HealthResponse(
        status="ok",
        mysql=_check_mysql(),
        milvus=_check_milvus(),
        llm=_check_llm(),
        checkpoint=_check_checkpointer(),
        redis=_check_redis(),
        config_loaded=True,
        llm_model=settings.DEEPSEEK_MODEL,
        rag_engine=settings.RAG_ENGINE,
        milvus_dim=settings.MILVUS_DIM,
        checkpoint_backend=settings.CHECKPOINT_BACKEND,
        mysql_db=settings.MYSQL_DB,
    )
