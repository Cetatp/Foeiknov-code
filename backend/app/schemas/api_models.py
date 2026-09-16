"""
API 请求/响应 Pydantic 模型。
"""
from typing import Optional, List, Any, Literal
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求（SSE 流式入口）。"""
    message: str = Field(default="", description="用户消息", max_length=2000)
    session_id: str = Field(default="default", description="会话 ID", max_length=64)
    stream: bool = Field(default=True, description="是否流式返回（SSE）")


class SpotQuery(BaseModel):
    keyword: Optional[str] = Field(default=None, description="关键词模糊匹配 spot_name/address")
    spot_level: Optional[str] = Field(default=None, description="级别过滤：5A/4A/3A")
    area_tag: Optional[str] = Field(default=None, description="区域过滤")
    limit: int = Field(default=20, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class HealthResponse(BaseModel):
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
    description: Optional[str] = None
    travel_tips: Optional[str] = None
    cultural_context: Optional[str] = None
    avg_visit_hours: Optional[float] = None


class SpotListResponse(BaseModel):
    total: int
    items: List[SpotBrief]


class TokenEvent(BaseModel):
    text: str
    module: Optional[str] = None


class StructureReadyEvent(BaseModel):
    type: Literal["plan_card", "advice_panel", "nearby_list", "qa_card"]
    payload: Any


class EndEvent(BaseModel):
    final_answer: str
    session_id: str
    citations: List[Any] = Field(default_factory=list)
