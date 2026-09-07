"""
配置中心
基于 Pydantic Settings 实现类型安全的配置管理，支持 .env 文件注入与环境变量覆盖。
全项目单例：from app.config import settings
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置单例，字段与 .env 一一对应。"""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # ===== LLM（DeepSeek）=====
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"           # 快速模式：deepseek-chat → V4-Flash 非思考
    DEEPSEEK_MODEL_PRO: str = "deepseek-v4-pro"     # 专家模式：V4-Pro
    DEEPSEEK_MODEL_REASONER: str = "deepseek-reasoner"  # 深度思考：reasoner → V4-Flash 思考模式
    DEEPSEEK_MODEL_VISION: str = "deepseek-v4-flash-vision-exp"  # 识图模式：视觉理解
    DEEPSEEK_TEMPERATURE: float = 0.3

    # ===== 高德地图 API =====
    AMAP_API_KEY: str = ""

    # ===== MySQL =====
    DB_TYPE: str = "mysql"
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "chengdu_travel"
    MYSQL_CHARSET: str = "utf8mb4"

    # ===== Redis =====
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # ===== RAG（LlamaIndex + Milvus）=====
    RAG_ENGINE: str = "llamaindex"
    RAG_TOP_K: int = 5
    MILVUS_DB_PATH: str = "127.0.0.1:19530"
    MILVUS_DB_NAME: str = "chengdu_travel_agent"
    MILVUS_COLLECTION_SPOTS: str = "chengdu_spots"
    MILVUS_DIM: int = 1024

    # ===== LTM 长期用户画像记忆 =====
    MILVUS_COLLECTION_LTM: str = "user_ltm_v1"
    LTM_SEMANTIC_TOP_K: int = 3
    LTM_DEDUP_THRESHOLD: float = 0.92

    # ===== Embedding 模型 =====
    EMBED_MODEL_NAME: str = "BAAI/bge-large-zh-v1.5"
    EMBED_DEVICE: str = "cpu"
    RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-large"

    # ===== 服务端口 =====
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 5173

    # ===== 认证（JWT）=====
    JWT_SECRET_KEY: str = "chengdu-travel-agent-secret-key-change-in-production-2026"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天
    JWT_ISSUER: str = "chengdu-travel-agent"

    # ===== 日志 =====
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"

    # ===== LangSmith 全链路追踪（已启用） =====
    LANGCHAIN_TRACING_V2: str = "true"
    LANGCHAIN_API_KEY: str = ""  # 真实值从 backend/.env 注入，勿硬编码
    LANGCHAIN_PROJECT: str = "chengdu-travel-agent"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"

    # ===== Checkpointer 跨会话持久化 =====
    CHECKPOINT_BACKEND: str = "sqlite"  # sqlite | memory | redis | postgres
    CHECKPOINT_SQLITE_DIR: str = "./data/checkpoints"
    CHECKPOINT_SQLITE_PATH: str = "./data/checkpoints/langgraph_checkpoints.db"
    CHECKPOINT_REDIS_TTL: int = 3600
    CHECKPOINT_POSTGRES_URI: str = ""

    # ===== Rolling Summary 阈值 =====
    ROLLING_WINDOW_MAX_TOKENS: int = 12000
    ROLLING_RECENT_ROUNDS: int = 6

    @property
    def mysql_url(self) -> str:
        """SQLAlchemy MySQL 连接 URL。"""
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
            f"?charset={self.MYSQL_CHARSET}"
        )

    @property
    def redis_url(self) -> str:
        """Redis 连接 URL。"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def langsmith_enabled(self) -> bool:
        """LangSmith 是否启用。"""
        return self.LANGCHAIN_TRACING_V2.lower() in ("true", "1", "yes")

    @property
    def is_milvus_lite(self) -> bool:
        """是否使用 Milvus Lite（本地文件模式）。"""
        return self.MILVUS_DB_PATH.endswith(".db")

    @property
    def milvus_uri(self) -> str:
        """Milvus 连接 URI（兼容 Lite 文件路径与 Standalone 地址）。"""
        if self.is_milvus_lite:
            return self.MILVUS_DB_PATH
        # Standalone 模式：host:port → http://host:port
        if self.MILVUS_DB_PATH.startswith("http"):
            return self.MILVUS_DB_PATH
        return f"http://{self.MILVUS_DB_PATH}"


# 全项目单例
settings = Settings()
