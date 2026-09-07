"""
LLM 客户端 — 统一 ChatOpenAI 封装 DeepSeek 多模型

支持模型：
- deepseek-chat       → V4-Flash 非思考模式（快速）
- deepseek-v4-pro     → V4-Pro（专家，强推理）
- deepseek-reasoner   → V4-Flash 思考模式（深度思考，带 reasoning）
- deepseek-v4-flash-vision-exp → 视觉理解（识图）

提供 get_llm(mode, deep_think) 工厂函数，按前端模式选择对应模型。
"""
from langchain_openai import ChatOpenAI
from app.config import settings


def _make_llm(model: str, temperature: float = 0.3, streaming: bool = True, **kwargs) -> ChatOpenAI:
    """创建单个 ChatOpenAI 实例。"""
    return ChatOpenAI(
        model=model,
        base_url=settings.DEEPSEEK_BASE_URL,
        api_key=settings.DEEPSEEK_API_KEY,
        temperature=temperature,
        max_tokens=getattr(settings, "DEEPSEEK_MAX_TOKENS", 4096),
        max_retries=3,
        timeout=120,
        streaming=streaming,
        **kwargs,
    )


# ── 各模式模型实例 ──
llm = _make_llm(settings.DEEPSEEK_MODEL)                       # 快速模式
llm_pro = _make_llm(settings.DEEPSEEK_MODEL_PRO, temperature=0.7)  # 专家模式
llm_reasoner = _make_llm(settings.DEEPSEEK_MODEL_REASONER, temperature=0.7)  # 深度思考
llm_vision = _make_llm(settings.DEEPSEEK_MODEL_VISION, temperature=0.3)  # 识图模式

# 结构化输出（JSON Mode），用于 Supervisor 意图分类 / Plan JSON 生成
# ★ 必须 non-streaming，否则 JSON 输出会泄漏到聊天流式响应中
llm_json = _make_llm(settings.DEEPSEEK_MODEL, temperature=0.1, streaming=False).bind(
    response_format={"type": "json_object"}
)

# Worker 专用 LLM（non-streaming）
# 用于 advice_worker 等节点，其输出以卡片形式展示，不应流式泄漏到聊天
llm_worker = _make_llm(settings.DEEPSEEK_MODEL, streaming=False)


def get_llm(mode: str = "fast", deep_think: bool = False) -> ChatOpenAI:
    """
    根据前端模式选择 LLM 实例。

    Args:
        mode: "fast" | "expert" | "vision"
        deep_think: 是否开启深度思考

    Returns:
        ChatOpenAI 实例
    """
    # 深度思考优先级最高（覆盖模式）
    if deep_think:
        return llm_reasoner

    if mode == "expert":
        return llm_pro
    elif mode == "vision":
        return llm_vision
    else:  # fast
        return llm


def get_llm_json(mode: str = "fast", deep_think: bool = False):
    """获取带 JSON 输出绑定的 LLM（用于结构化任务，non-streaming）。"""
    base = get_llm(mode, deep_think)
    return base.bind(response_format={"type": "json_object"}, streaming=False)
