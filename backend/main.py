"""
FastAPI 后端入口
启动时加载配置中心 & 日志系统，注册路由，提供健康检查接口。
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时注入 LangSmith 环境变量并打印配置。"""
    # ★ LangSmith 全链路追踪（零代码侵入，环境变量一开 LangChain/LangGraph 自动 trace）
    if settings.langsmith_enabled:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
        os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
        logger.info("  LangSmith 环境变量已注入 → https://smith.langchain.com/")

    logger.info("=" * 60)
    logger.info("蓉游智体 · PandaAgent 后端服务启动")
    logger.info(f"  LLM 模型: {settings.DEEPSEEK_MODEL}")
    logger.info(f"  RAG 引擎: {settings.RAG_ENGINE}")
    logger.info(f"  MySQL: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}")
    logger.info(f"  Milvus: {settings.MILVUS_DB_PATH}")
    logger.info(f"  Checkpointer: {settings.CHECKPOINT_BACKEND}")
    logger.info(f"  LangSmith: {'✅ 启用 → ' + settings.LANGCHAIN_PROJECT if settings.langsmith_enabled else '关闭'}")
    logger.info("=" * 60)
    yield
    logger.info("后端服务关闭")


app = FastAPI(
    title="成都旅游智能体 API",
    version="1.0.0",
    lifespan=lifespan,
)


# ★ 注册路由
from app.api.chat_routes import router as chat_router
from app.api.spot_routes import router as spot_router
app.include_router(chat_router)
app.include_router(spot_router)


@app.get("/health")
async def health_check():
    """健康检查：返回服务状态与关键配置（脱敏）。"""
    return {
        "status": "ok",
        "config_loaded": True,
        "llm_model": settings.DEEPSEEK_MODEL,
        "rag_engine": settings.RAG_ENGINE,
        "milvus_dim": settings.MILVUS_DIM,
        "checkpoint_backend": settings.CHECKPOINT_BACKEND,
        "mysql_db": settings.MYSQL_DB,
        "log_level": settings.LOG_LEVEL,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True,
    )
