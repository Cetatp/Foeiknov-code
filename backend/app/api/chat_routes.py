"""
聊天路由 — POST /api/chat（SSE 流式核心）
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
    if not text:
        return text
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        s = line.replace("**", "")
        if not re.match(r"^\s*[-*]\s+", s):
            s = s.replace("*", "")
        s = s.replace("`", "")
        if re.match(r"^\s*[-*_]{3,}\s*$", s):
            continue
        cleaned.append(s)
    result = "\n".join(cleaned)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


WORKER_CARD_MAP = {
    "plan_worker": "plan_card",
    "advice_worker": "advice_panel",
    "nearby_worker": "nearby_list",
    "qa_worker": "qa_card",
}


@router.post("/api/chat")
async def chat_stream(req: ChatRequest):
    import uuid as _uuid
    import time as _time

    thread_id = f"{req.session_id}_{int(_time.time()*1000)}_{_uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "messages": [{"role": "user", "content": req.message}],
        "phase": "routing",
        "final_answer": "",
        "worker_results": {},
    }

    async def event_generator():
        final_answer = ""
        emitted_workers = set()
        try:
            async with get_checkpointer_async() as saver:
                graph = build_graph(saver)
                async for event in graph.astream_events(initial_state, config, version="v2"):
                    event_type = event.get("event")

                    if event_type == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content"):
                            token = chunk.content
                            if token:
                                yield (
                                    f"event: token\n"
                                    f"data: {json.dumps({'text': _clean_markdown(token)}, ensure_ascii=False)}\n\n"
                                )

                    elif event_type == "on_chain_end":
                        output = event.get("data", {}).get("output", {})
                        if not isinstance(output, dict):
                            continue

                        if "worker_results" in output:
                            for worker_name, content in output["worker_results"].items():
                                if worker_name in emitted_workers:
                                    continue
                                card_type = WORKER_CARD_MAP.get(worker_name)
                                if card_type:
                                    emitted_workers.add(worker_name)
                                    clean_content = _clean_markdown(content) if isinstance(content, str) else content
                                    yield (
                                        f"event: structure_ready\n"
                                        f"data: {json.dumps({'type': card_type, 'payload': clean_content}, ensure_ascii=False)}\n\n"
                                    )

                        if "final_answer" in output:
                            final_answer = _clean_markdown(output["final_answer"])

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
