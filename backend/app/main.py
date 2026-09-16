"""
FastAPI 后端入口 — 阶段 7

技术要点：
- CORS 精确白名单 http://localhost:5173（不能 * + allow_credentials）
- startup 事件预热 LLM / Embedding / DB 连接，避免冷启动卡顿
- 路由模块化：health_routes / spot_routes / chat_routes
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时预热，关闭时清理。"""
    logger.info("=" * 60)
    logger.info("蓉游智体 PandaAgent后端服务启动")
    logger.info(f"  LLM 模型: {settings.DEEPSEEK_MODEL}")
    logger.info(f"  RAG 引擎: {settings.RAG_ENGINE}")
    logger.info(f"  MySQL: {settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}")
    logger.info(f"  Milvus: {settings.MILVUS_DB_PATH}")
    logger.info(f"  Checkpointer: {settings.CHECKPOINT_BACKEND}")
    logger.info(f"  LangSmith: {'启用' if settings.langsmith_enabled else '关闭'}")
    logger.info(f"  端口: {settings.BACKEND_PORT}")
    logger.info("=" * 60)

    # ── startup 预热：触发 LLM / Embedding / DB 连接初始化 ──
    try:
        from app.database.mysql_client import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ MySQL 连接预热完成")
    except Exception as e:
        logger.warning(f"⚠️ MySQL 预热失败（可能服务未启动）：{e}")

    try:
        # 只 import，不实际调用（避免加载 BGE 模型浪费 30 秒）
        from app.agents.llm_client import llm  # noqa: F401
        logger.info("✅ LLM 客户端初始化完成（API Key 已配置）")
    except Exception as e:
        logger.warning(f"⚠️ LLM 初始化失败：{e}")

    try:
        # ★ 关键：预热 LlamaIndex Settings，确保第一个 Worker 调用时
        #    Settings._embed_model 已被设为 BGE EmbeddingService，
        #    而不是 None（否则 resolve_embed_model 会尝试 OpenAI 并炸掉）
        from app.rag.llama_index_engine import _ensure_settings
        _ensure_settings()
        logger.info("✅ LlamaIndex Settings 预热完成（BGE Embedding 已绑定）")
    except Exception as e:
        logger.warning(f"⚠️ LlamaIndex Settings 预热失败：{e}")

    yield

    logger.info("后端服务关闭")


app = FastAPI(
    title="蓉游智体 PandaAgent API",
    version="1.0.0",
    lifespan=lifespan,
    description="""
蓉游智体 AI Agent 后端服务

**三大核心能力**：
- 🏥 `GET /health` — 全链路健康检查（MySQL / Milvus / LLM / Checkpointer）
- 📍 `GET /api/spots` — 1554 景点搜索 / 过滤 / 分页
- 💬 `POST /api/chat` — SSE 流式 Agent 对话（Supervisor + 4 Worker 并行）
""",
)

# ── CORS 中间件 ──
# ★ 穿透模式：allow_origins=["*"]，穿透域名不固定无法逐个加白
# 前端走 Vite proxy 时浏览器不会发 CORS，但穿透后直连后端必须放开
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册路由 ──
from app.api.health_routes import router as health_router
from app.api.spot_routes import router as spot_router
from app.api.chat_routes import router as chat_router

app.include_router(health_router)   # GET  /health
app.include_router(spot_router)     # GET  /api/spots, /api/spots/{id}
app.include_router(chat_router)     # POST /api/chat


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True,
    )
