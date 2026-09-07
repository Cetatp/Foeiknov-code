"""
API 请求/响应 Pydantic 模型

SSE 事件类型（前端对应解析）：
- event: token            → 增量文本 token
- event: structure_ready  → 结构化卡片（PlanCard / AdvicePanel / NearbyList / QACard）
- event: end              → 最终答案 + session_id + 引用
"""
from typing import Optional, List, Any, Literal
from pydantic import BaseModel, Field


# ── 请求模型 ──

class ChatRequest(BaseModel):
    """聊天请求（SSE 流式入口）。"""
    message: str = Field(default="", description="用户消息", max_length=2000)
    session_id: str = Field(default="default", description="会话 ID（用于 Checkpointer 持久化）", max_length=64)
    stream: bool = Field(default=True, description="是否流式返回（SSE）")
    mode: Literal["fast", "expert", "vision"] = Field(default="fast", description="运行模式：快速/专家/识图")
    deep_think: bool = Field(default=False, description="是否开启深度思考")
    smart_search: bool = Field(default=False, description="是否开启智能搜索（联网）")
    image: Optional[str] = Field(default=None, description="图片 base64 dataURL（识图模式使用）")


class SpotQuery(BaseModel):
    """景点列表查询参数。"""
    keyword: Optional[str] = Field(default=None, description="关键词模糊匹配 spot_name/address")
    spot_level: Optional[str] = Field(default=None, description="级别过滤：5A/4A/3A")
    area_tag: Optional[str] = Field(default=None, description="区域过滤：成华区/武侯区...")
    limit: int = Field(default=20, ge=1, le=200, description="返回条数")
    offset: int = Field(default=0, ge=0, description="偏移量")


# ── 响应模型 ──

class HealthResponse(BaseModel):
    """健康检查响应。"""
    status: str
    mysql: str
    milvus: str
    llm: str
    checkpoint: str
    redis: str = Field(default="skipped")
    config_loaded: bool
    llm_model: str
    rag_engine: str
    milvus_dim: int
    checkpoint_backend: str
    mysql_db: str


class SpotBrief(BaseModel):
    """景点简要信息（列表用）。"""
    spot_id: int
    spot_name: str
    spot_level: Optional[str] = None
    address: Optional[str] = None
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    rating: Optional[float] = None
    ticket_price_min: Optional[int] = None
    area_tag: Optional[str] = None


class SpotDetail(SpotBrief):
    """景点详情（单条查询用，含 description/travel_tips/cultural_context）。"""
    description: Optional[str] = None
    travel_tips: Optional[str] = None
    cultural_context: Optional[str] = None
    avg_visit_hours: Optional[float] = None


class SpotListResponse(BaseModel):
    """景点列表响应。"""
    total: int
    items: List[SpotBrief]


# ── SSE 事件载荷 ──

class TokenEvent(BaseModel):
    """增量 token 事件。"""
    text: str
    module: Optional[str] = None


class StructureReadyEvent(BaseModel):
    """结构化卡片事件（先于 final_answer 推送，前端直接渲染）。"""
    type: Literal["plan_card", "advice_panel", "nearby_list", "qa_card"]
    payload: Any


class EndEvent(BaseModel):
    """最终答案事件。"""
    final_answer: str
    session_id: str
    citations: List[Any] = Field(default_factory=list)
