"""
LangGraph 节点 — Supervisor + 4 Worker

- supervisor：多意图分类 → Send API 并行路由 → 汇总输出
- qa_worker：RAG 问答
- plan_worker：规则注入 + LLM 生成 + validate_plan 校验
- advice_worker：避坑规则注入 + LLM 建议
- nearby_worker：MySQL 坐标 + Bounding Box + Haversine
"""
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError, OperationalError
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.schemas.agent_models import MultiAgentState
from app.agents.llm_client import llm, llm_json, llm_worker
from app.agents.utils import validate_plan, haversine, safe_json_loads
from app.database.mysql_client import engine
from app.rag.llama_index_engine import build_query_engine
from app.rag.prompt_templates import (
    SUPERVISOR_PROMPT, PLAN_PROMPT, ADVICE_PROMPT,
    NEARBY_PROMPT, SUPERVISOR_SUMMARY_PROMPT,
)
from app.tools.amap_weather import get_weather, is_weather_query
from app.logger import logger

VALID_WORKERS = {"qa_worker", "plan_worker", "advice_worker", "nearby_worker"}


def _clean_markdown(text: str) -> str:
    if not text:
        return text
    import re as _re
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        s = line.replace("**", "")
        if not _re.match(r"^\s*[-*]\s+", s):
            s = s.replace("*", "")
        s = s.replace("`", "")
        if _re.match(r"^\s*[-*_]{3,}\s*$", s):
            continue
        cleaned.append(s)
    result = "\n".join(cleaned)
    return _re.sub(r"\n{3,}", "\n\n", result).strip()


GREETING_PATTERNS = [
    "你好", "您好", "hi", "hello", "hey", "在吗", "在不在",
    "你是谁", "你叫什么", "介绍一下你自己", "你能做什么", "你会什么",
    "谢谢", "感谢", "thanks", "thank you", "再见", "拜拜", "bye",
    "早上好", "下午好", "晚上好",
]


def _is_greeting(msg: str) -> bool:
    m = msg.strip().lower()
    return len(m) <= 10 and any(p in m for p in GREETING_PATTERNS)


def _greeting_response(msg: str) -> str:
    m = msg.strip().lower()
    if any(k in m for k in ["你是谁", "你叫什么", "介绍一下你自己", "你能做什么", "你会什么"]):
        return (
            "你好！我是蓉游智体 PandaAgent 🐼\n\n"
            "我可以帮你查询成都景点信息、规划多日行程、提供避坑建议和周边景点推荐。"
        )
    if any(k in m for k in ["谢谢", "感谢", "thanks", "thank you"]):
        return "不客气！祝你在成都玩得开心 🎉"
    if any(k in m for k in ["再见", "拜拜", "bye"]):
        return "再见！期待下次为你服务 👋"
    return "你好！我是蓉游智体 PandaAgent 🐼 有什么可以帮你的吗？"


def _last_user_message(state: MultiAgentState) -> str:
    for m in reversed(state.get("messages", [])):
        if m.type == "human":
            return m.content
    return ""


def _safe_worker_result(worker_name: str, content) -> dict:
    return {"worker_results": {worker_name: content}}


async def supervisor(state: MultiAgentState) -> dict:
    """首轮做路由，Worker 完成后第二轮做结果汇总。"""
    phase = state.get("phase", "routing")
    worker_results = state.get("worker_results") or {}
    user_msg = _last_user_message(state)

    if phase == "summary" or worker_results:
        if not worker_results:
            direct = _greeting_response(user_msg)
            return {
                "phase": "summary",
                "next_workers": [],
                "final_answer": direct,
                "messages": [AIMessage(content=direct)],
            }

        summary = "\n\n".join(
            f"【{name}】\n{content}" for name, content in worker_results.items()
        )
        try:
            prompt = SUPERVISOR_SUMMARY_PROMPT.format(worker_results=summary)
            response = await llm.ainvoke([
                SystemMessage(content=prompt),
                HumanMessage(content="请整合以上信息，给出最终回答。"),
            ])
            final = response.content
            logger.info(f"Supervisor 汇总完成，共 {len(worker_results)} 个 Worker 结果")
        except Exception as e:
            logger.error(f"Supervisor 汇总 LLM 调用失败: {e}")
            final = summary

        return {
            "phase": "summary",
            "next_workers": [],
            "final_answer": final,
            "messages": [AIMessage(content=final)],
        }

    reset = {"worker_results": {}, "final_answer": ""}

    if _is_greeting(user_msg):
        direct = _greeting_response(user_msg)
        return {
            **reset,
            "phase": "routing",
            "next_workers": [],
            "final_answer": direct,
            "messages": [AIMessage(content=direct)],
        }

    if is_weather_query(user_msg):
        weather_info = get_weather("成都", extensions="all")
        prompt = (
            f"用户询问：{user_msg}\n\n"
            f"以下是高德地图提供的成都天气数据：\n{weather_info}\n\n"
            "请根据以上天气数据，用友好的语气回答用户的问题，并给出必要的出行建议。"
        )
        try:
            response = await llm.ainvoke([
                SystemMessage(content="你是蓉游智体 PandaAgent，根据天气数据为用户提供出行建议。"),
                HumanMessage(content=prompt),
            ])
            final = _clean_markdown(response.content)
        except Exception as e:
            logger.error(f"天气回答生成失败: {e}")
            final = weather_info
        return {
            **reset,
            "phase": "routing",
            "next_workers": [],
            "final_answer": final,
            "messages": [AIMessage(content=final)],
        }

    try:
        response = await llm_json.ainvoke([
            SystemMessage(content=SUPERVISOR_PROMPT),
            HumanMessage(content=user_msg),
        ])
        result = safe_json_loads(response.content, {})
        next_workers = result.get("next_workers", [])
    except Exception as e:
        logger.error(f"Supervisor 意图分类 LLM 调用失败: {e}")
        next_workers = ["qa_worker"]

    next_workers = [w for w in dict.fromkeys(next_workers) if w in VALID_WORKERS]
    if not next_workers:
        next_workers = ["qa_worker"]

    logger.info(f"Supervisor 意图分类: {user_msg[:30]}... → {next_workers}")
    return {**reset, "phase": "routing", "next_workers": next_workers}


async def qa_worker(state: MultiAgentState) -> dict:
    user_msg = _last_user_message(state)
    try:
        query_engine = build_query_engine()
        response = await query_engine.aquery(user_msg)
        content = str(response).strip()
        is_empty = (
            not content
            or content.lower() in ("empty response", "none", "null")
            or "知识库中暂无" in content
        )
        if is_empty:
            fallback_prompt = (
                "你是蓉游智体 PandaAgent，基于成都旅游通用知识回答用户问题。\n"
                "涉及具体票价、开放时间等精确数字时，请说明是参考信息并建议以官方公告为准。\n"
                "用数字序号列表回答，不要写开场白或结尾语。"
            )
            resp = await llm_worker.ainvoke([
                SystemMessage(content=fallback_prompt),
                HumanMessage(content=user_msg),
            ])
            content = resp.content.strip()
    except Exception as e:
        logger.error(f"qa_worker 失败: {e}")
        content = f"（QA 检索暂不可用：{e}）"
    return _safe_worker_result("qa_worker", content)


async def plan_worker(state: MultiAgentState) -> dict:
    user_msg = _last_user_message(state)
    rules_text = "（暂无硬规则数据）"
    transit_text = "（暂无通勤数据）"
    templates_text = "（无行程模板）"

    try:
        with engine.connect() as conn:
            hard_rules = conn.execute(
                text("SELECT rule_content, reason, priority FROM hard_rules ORDER BY priority ASC")
            ).fetchall()
            if hard_rules:
                rules_text = "\n".join([f"- {r[0]}（原因：{r[1]}）" for r in hard_rules])

            transit = conn.execute(
                text("SELECT from_spot_name, to_spot_name, transit_mode, duration_min "
                     "FROM transit_matrix WHERE same_region=1 LIMIT 20")
            ).fetchall()
            if transit:
                transit_text = "\n".join(
                    [f"{t[0]}→{t[1]} ({t[2]}): {t[3]}分钟" for t in transit]
                )

            try:
                templates = conn.execute(
                    text("SELECT template_json FROM itinerary_templates LIMIT 5")
                ).fetchall()
                if templates:
                    templates_text = "\n".join([f"模板{i+1}: {t[0]}" for i, t in enumerate(templates)])
            except (ProgrammingError, OperationalError):
                pass
    except Exception as e:
        logger.warning(f"plan_worker: MySQL 查询失败，降级为无规则模式：{e}")

    try:
        prompt = PLAN_PROMPT.format(
            hard_rules=rules_text,
            transit_matrix=transit_text,
            templates=templates_text,
        )
        response = await llm_json.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=user_msg),
        ])
        plan = validate_plan(safe_json_loads(response.content, {}))
        content = plan
    except Exception as e:
        logger.error(f"plan_worker 失败: {e}")
        content = {"error": f"行程规划失败：{e}"}

    return _safe_worker_result("plan_worker", content)


async def advice_worker(state: MultiAgentState) -> dict:
    user_msg = _last_user_message(state)
    rules_text = "（暂无避坑规则数据）"
    try:
        with engine.connect() as conn:
            high_rules = conn.execute(
                text("SELECT title, content FROM avoid_rules WHERE severity='high' LIMIT 15")
            ).fetchall()
            if high_rules:
                rules_text = "\n".join([f"- {r[0]}：{r[1]}" for r in high_rules])
    except Exception as e:
        logger.warning(f"advice_worker: 避坑规则查询失败，降级为无规则模式：{e}")

    try:
        prompt = ADVICE_PROMPT.format(avoid_rules=rules_text)
        response = await llm_worker.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=user_msg),
        ])
        content = response.content
    except Exception as e:
        logger.error(f"advice_worker 失败: {e}")
        content = f"（建议生成暂不可用：{e}）"

    return _safe_worker_result("advice_worker", content)


async def nearby_worker(state: MultiAgentState) -> dict:
    user_msg = _last_user_message(state)
    try:
        response = await llm_json.ainvoke([
            SystemMessage(content=NEARBY_PROMPT),
            HumanMessage(content=user_msg),
        ])
        result = safe_json_loads(response.content, {})
        target_spot = result.get("spot_name", "")
        radius_km = float(result.get("radius_km", 5))

        if not target_spot:
            return _safe_worker_result("nearby_worker", "未能识别景点名称")

        with engine.connect() as conn:
            target = conn.execute(
                text("SELECT longitude, latitude FROM spots WHERE spot_name=:name"),
                {"name": target_spot},
            ).fetchone()
            if not target:
                return _safe_worker_result("nearby_worker", f"未找到景点：{target_spot}")

            lon, lat = float(target[0]), float(target[1])
            delta = radius_km / 111.0
            all_spots = conn.execute(
                text("""
                    SELECT spot_name, longitude, latitude, rating FROM spots
                    WHERE longitude BETWEEN :lon_min AND :lon_max
                      AND latitude BETWEEN :lat_min AND :lat_max
                """),
                {
                    "lon_min": lon - delta,
                    "lon_max": lon + delta,
                    "lat_min": lat - delta,
                    "lat_max": lat + delta,
                },
            ).fetchall()

        nearby = []
        for s in all_spots:
            if s[1] is None or s[2] is None:
                continue
            dist = haversine(lon, lat, float(s[1]), float(s[2]))
            if 0 < dist <= radius_km:
                nearby.append({
                    "name": s[0],
                    "distance_km": round(dist, 1),
                    "rating": float(s[3]) if s[3] else 0,
                })
        nearby.sort(key=lambda x: x["distance_km"])
        content = nearby[:10]
    except Exception as e:
        logger.error(f"nearby_worker 失败: {e}")
        content = {"error": f"周边推荐失败：{e}"}

    return _safe_worker_result("nearby_worker", content)
