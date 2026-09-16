"""
LLM 客户端 — 统一 ChatOpenAI 封装 DeepSeek。

项目只保留一个默认模型；另外保留 JSON 与 Worker 两种内部调用配置，
它们不是用户可选择的运行模式。
"""
from langchain_openai import ChatOpenAI
from app.config import settings


def _make_llm(model: str, temperature: float = 0.3, streaming: bool = True, **kwargs) -> ChatOpenAI:
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


# 面向用户最终回答的默认流式模型
llm = _make_llm(settings.DEEPSEEK_MODEL)

# 内部结构化任务：Supervisor 意图分类 / Plan JSON / Nearby 参数提取
llm_json = _make_llm(
    settings.DEEPSEEK_MODEL,
    temperature=0.1,
    streaming=False,
).bind(response_format={"type": "json_object"})

# Worker 内部完整文本生成，不向前端泄漏中间 token
llm_worker = _make_llm(settings.DEEPSEEK_MODEL, streaming=False)
