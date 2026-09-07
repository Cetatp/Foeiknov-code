"""
聊天路由 — POST /api/chat（SSE 流式核心）

SSE 输出格式（前端对应解析）：

    event: token
    data: {"text":"今天","module":"plan"}

    event: structure_ready    # ★ 先于 final_answer 推送，前端直接渲染 PlanCard/AdvicePanel
    data: {"type":"plan_card", "payload": PlanResult对象}

    event: end
    data: {"final_answer":"完整Markdown","session_id":"...","citations":[]}

技术要点：
- 只用一次 astream_events（避免 Checkpointer 恢复导致 Worker 跳过）
- astream_events 里从 Supervisor 的 on_chain_end 提取 final_answer
- Token 级增量推送 + 结构化卡片先行 + Checkpointer 跨会话持久化
"""
import json
import re

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agents.graph import build_graph
from app.database.checkpoint_factory import get_checkpointer_async
from app.schemas.api_models import ChatRequest
from app.logger import logger

router = APIRouter(tags=["chat"])


def _clean_markdown(text: str) -> str:
    """
    ★ 轻量清洗：保留 Markdown 结构（## 标题 / - 列表 / 1. 列表 / 表格 / > 引用 / 空行），
    只删除 **加粗**、`代码`、--- 分隔线 等前端不渲染的标记。
    保留 emoji、○ 子项、| 表格分隔符、> 引用标记。
    """
    if not text:
        return text
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        s = line
        # 去除加粗标记 **（保留列表前缀 - 或 *）
        s = s.replace("**", "")
        # 去除行内 *（不是列表开头的 - 或 *）
        if not re.match(r"^\s*[-*]\s+", s):
            s = s.replace("*", "")
        # 去除代码标记
        s = s.replace("`", "")
        # 跳过分隔线行（--- / *** / ___）
        if re.match(r"^\s*[-*_]{3,}\s*$", s):
            continue
        # ★ 保留：## 标题、- 列表、1. 列表、| 表格、> 引用、emoji、○ 子项、空行
        cleaned.append(s)
    result = "\n".join(cleaned)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()

# Worker → 卡片类型映射（前端渲染用）
WORKER_CARD_MAP = {
    "plan_worker": "plan_card",
    "advice_worker": "advice_panel",
    "nearby_worker": "nearby_list",
    "qa_worker": "qa_card",
}


@router.post("/api/chat")
async def chat_stream(req: ChatRequest):
    """
    SSE 流式聊天入口。

    - Supervisor 意图分类 → Send API 并行 fan-out → Worker 执行 → 汇总输出
    - Token 级增量推送 + 结构化卡片先行 + Checkpointer 跨会话持久化
    """
    import uuid as _uuid
    import time as _time
    # ★ 每次请求用唯一 thread_id —— Checkpointer 只在单次请求内有效，跨请求永不串状态
    _thread_id = f"{req.session_id}_{int(_time.time()*1000)}_{_uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": _thread_id}}
    logger.info(f"[CHECKPOINT] session_id={req.session_id} → unique thread_id={_thread_id}")

    # ★ 重置 Checkpointer 恢复的旧中间状态——否则 Supervisor 会用上次的 phase/summary/worker_results
    initial_state = {
        "messages": [{"role": "user", "content": req.message}],
        "mode": req.mode,
        "deep_think": req.deep_think,
        "smart_search": req.smart_search,
        "image": req.image,
        "phase": "routing",       # 无 reducer，直接覆盖 checkpoint 旧值
        "final_answer": "",        # 无 reducer，直接覆盖
        "worker_results": {},      # merge_results reducer 遇空字典清空
    }

    async def event_generator():
        final_answer = ""
        emitted_workers = set()  # ★ 去重：同一个 worker 只推一次卡片
        try:
            async with get_checkpointer_async() as saver:
                graph = build_graph(saver)

                # ★ 只用 astream_events 一次，避免 Checkpointer 恢复导致 Worker 跳过
                async for event in graph.astream_events(
                    initial_state,
                    config,
                    version="v2",
                ):
                    event_type = event.get("event")

                    # 1. Token 增量推送（LLM 流式输出）
                    if event_type == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content"):
                            token = chunk.content
                            if token:
                                token = _clean_markdown(token)  # ★ 清洗 Markdown
                                yield (
                                    f"event: token\n"
                                    f"data: {json.dumps({'text': token}, ensure_ascii=False)}\n\n"
                                )

                    # 2. on_chain_end：Worker 完成 → 推卡片；Supervisor 汇总 → 取 final_answer
                    elif event_type == "on_chain_end":
                        output = event.get("data", {}).get("output", {})
                        if isinstance(output, dict):
                            # ★ 深度思考过程 → 推 reasoning 事件
                            if "reasoning" in output and output["reasoning"]:
                                yield (
                                    f"event: reasoning\n"
                                    f"data: {json.dumps({'text': output['reasoning']}, ensure_ascii=False)}\n\n"
                                )
                            # Worker 结果 → 推 structure_ready 卡片
                            if "worker_results" in output:
                                results = output["worker_results"]
                                for worker_name, content in results.items():
                                    # ★ 去重：同一 worker 只推一次（图级 on_chain_end 会带累积 state）
                                    if worker_name in emitted_workers:
                                        continue
                                    card_type = WORKER_CARD_MAP.get(worker_name)
                                    if card_type:
                                        emitted_workers.add(worker_name)
                                        # ★ 清洗 Worker 输出中的 *
                                        clean_content = _clean_markdown(content) if isinstance(content, str) else content
                                        yield (
                                            f"event: structure_ready\n"
                                            f"data: {json.dumps({'type': card_type, 'payload': clean_content}, ensure_ascii=False)}\n\n"
                                        )
                            # Supervisor 最终回答
                            if "final_answer" in output:
                                final_answer = _clean_markdown(output["final_answer"])  # ★ 清洗 Markdown

            # 4. astream_events 结束后发 end 事件
            yield (
                f"event: end\n"
                f"data: {json.dumps({'final_answer': final_answer, 'session_id': req.session_id, 'citations': []}, ensure_ascii=False)}\n\n"
            )

        except Exception as e:
            logger.error(f"chat_stream 异常: {e}")
            yield (
                f"event: end\n"
                f"data: {json.dumps({'final_answer': f'抱歉，服务暂时不可用：{e}', 'session_id': req.session_id, 'citations': []}, ensure_ascii=False)}\n\n"
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
