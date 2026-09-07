"""
LangGraph 节点 — Supervisor + 4 Worker

节点设计：
- supervisor：多意图分类 → Send API 并行路由 → 汇总输出
- qa_worker：RAG 问答
- plan_worker：硬规则注入 + LLM 生成 + validate_plan 程序级强制
- advice_worker：六维建议（避坑规则注入）
- nearby_worker：Haversine 半径过滤周边景点
"""
import json
import re
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError, OperationalError
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.schemas.agent_models import MultiAgentState
from app.agents.llm_client import llm, llm_json, llm_worker, get_llm, get_llm_json
from app.agents.utils import validate_plan, haversine, safe_json_loads
from app.database.mysql_client import engine
from app.rag.llama_index_engine import build_query_engine
from app.rag.prompt_templates import (
    SUPERVISOR_PROMPT, PLAN_PROMPT, ADVICE_PROMPT,
    NEARBY_PROMPT, SUPERVISOR_SUMMARY_PROMPT,
)
from app.tools.web_search import web_search
from app.tools.amap_weather import get_weather, is_weather_query
from app.logger import logger

VALID_WORKERS = {"qa_worker", "plan_worker", "advice_worker", "nearby_worker"}


def _clean_markdown(text: str) -> str:
    """★ 轻量清洗：保留 Markdown 结构（## 标题 / - 列表 / 1. 列表 / 表格 / > 引用 / 空行），
    只删除 **加粗**、`代码`、--- 分隔线 等前端不渲染的标记。
    保留 emoji、○ 子项、| 表格分隔符、> 引用标记。"""
    if not text:
        return text
    import re as _re
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        s = line
        # 去除加粗/斜体标记（** 和 *），但不破坏 - 列表前缀
        s = s.replace("**", "")
        # 只清理行内 *（不是列表开头的 - 或 *）
        if not _re.match(r"^\s*[-*]\s+", s):
            s = s.replace("*", "")
        # 去除代码标记
        s = s.replace("`", "")
        # 跳过分隔线行（--- / *** / ___）
        if _re.match(r"^\s*[-*_]{3,}\s*$", s):
            continue
        # ★ 保留：## 标题、- 列表、1. 列表、| 表格、> 引用、emoji、○ 子项、空行
        cleaned.append(s)
    result = "\n".join(cleaned)
    result = _re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()

# 问候/闲聊关键词（不走 Worker，直接回答）
GREETING_PATTERNS = [
    "你好", "您好", "hi", "hello", "hey", "在吗", "在不在",
    "你是谁", "你叫什么", "介绍一下你自己", "你能做什么", "你会什么",
    "谢谢", "感谢", "thanks", "thank you",
    "再见", "拜拜", "bye",
    "早上好", "下午好", "晚上好",
]


def _is_greeting(msg: str) -> bool:
    """判断是否为问候/闲聊类消息。"""
    m = msg.strip().lower()
    if len(m) <= 10:  # 短消息大概率是问候
        for p in GREETING_PATTERNS:
            if p in m:
                return True
    return False


def _greeting_response(msg: str) -> str:
    """根据问候类型返回直接回答。"""
    m = msg.strip().lower()
    if any(k in m for k in ["你是谁", "你叫什么", "介绍一下你自己", "你能做什么", "你会什么"]):
        return (
            "你好！我是蓉游智体 PandaAgent 🐼 🐼\n\n"
            "我可以帮你：\n"
            "- 📖 查询成都景点信息（门票、开放时间、历史文化等）\n"
            "- 📋 规划成都多日行程（亲子/情侣/老人等）\n"
            "- 📍 推荐景点周边美食和景点\n"
            "- 💡 提供天气、预算、交通、避坑、美食、拍照六维建议\n\n"
            "直接告诉我你的需求吧～"
        )
    if any(k in m for k in ["谢谢", "感谢", "thanks", "thank you"]):
        return "不客气！祝你在成都玩得开心 🎉 有其他问题随时问我～"
    if any(k in m for k in ["再见", "拜拜", "bye"]):
        return "再见！期待下次为你服务 👋"
    return "你好！我是蓉游智体 PandaAgent 🐼 🐼 有什么可以帮你的吗？"


def _last_user_message(state: MultiAgentState) -> str:
    """取最近一条用户消息。"""
    for m in reversed(state.get("messages", [])):
        if m.type == "human":
            return m.content
    return ""


def _safe_worker_result(worker_name: str, content: str) -> dict:
    """统一 Worker 返回格式。"""
    return {"worker_results": {worker_name: content}}


# ── Supervisor：多意图分类 + 汇总 ──
async def supervisor(state: MultiAgentState) -> dict:
    """
    两轮职责（由 state["phase"] 或 worker_results 是否为空判断）：
    1. 首轮 phase="routing"（或 worker_results 为空）：意图分类 → 返回 next_workers
    2. 次轮 phase="summary"（或 worker_results 非空）：汇总各 Worker 结果
    """
    phase = state.get("phase", "routing")
    worker_results = state.get("worker_results") or {}

    # ★ DEBUG: 打印 Supervisor 入口 state（HTTP 层两轮对比用）
    _dbg = f"[SUPERVISOR-ENTER] phase={phase!r} wr_keys={list(worker_results.keys())} msg_count={len(state.get('messages',[]))}"
    print(_dbg, flush=True)
    logger.info(_dbg)

    # 第二轮：所有 Worker 执行完毕，汇总输出
    if phase == "summary" or worker_results:
        image = state.get("image")
        user_msg = _last_user_message(state)

        # ★ 识图模式：有图片时直接用 vision 模型分析，不走 Worker 汇总
        if image:
            try:
                # 强制使用 vision 模型
                vision_llm = get_llm("vision", False)
                # 多模态消息：文本 + 图片
                question = user_msg or "请描述这张图片的内容"
                human_content = [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": image}},
                ]
                response = await vision_llm.ainvoke([
                    SystemMessage(content="你是蓉游智体 PandaAgent，擅长识别景点、美食、路线图片。请用中文回答用户关于图片的问题。"),
                    HumanMessage(content=human_content),
                ])
                final = response.content
                logger.info(f"识图模式完成，用户消息: {user_msg[:30]}")
                return {
                    "phase": "summary",
                    "next_workers": [],
                    "final_answer": final,
                    "messages": [AIMessage(content=final)],
                }
            except Exception as e:
                logger.error(f"识图模型调用失败: {e}")
                return {
                    "phase": "summary",
                    "next_workers": [],
                    "final_answer": f"抱歉，图片识别失败：{str(e)}",
                    "messages": [AIMessage(content=f"抱歉，图片识别失败：{str(e)}")],
                }

        # ★ 无 Worker 结果（如问候语被直接处理）→ 不调用 LLM 编造
        if not worker_results:
            direct = _greeting_response(user_msg)
            logger.info(f"Supervisor 直接回答（无 Worker 结果）: {user_msg[:30]}")
            return {
                "phase": "summary",
                "next_workers": [],
                "final_answer": direct,
                "messages": [AIMessage(content=direct)],
            }

        summary_parts = []
        for name, content in worker_results.items():
            summary_parts.append(f"【{name}】\n{content}")
        summary = "\n\n".join(summary_parts)

        # ★ 智能搜索：联网检索最新信息，追加到上下文
        mode = state.get("mode", "fast")
        deep_think = state.get("deep_think", False)
        smart_search = state.get("smart_search", False)

        if smart_search:
            logger.info(f"智能搜索启用: {user_msg[:30]}")
            search_result = web_search(user_msg)
            if search_result:
                summary_parts.append(f"【联网搜索结果】\n{search_result}")
                summary = "\n\n".join(summary_parts)

        try:
            prompt = SUPERVISOR_SUMMARY_PROMPT.format(worker_results=summary)
            # ★ 根据模式选择 LLM
            summary_llm = get_llm(mode, deep_think)
            response = await summary_llm.ainvoke([
                SystemMessage(content=prompt),
                HumanMessage(content="请整合以上信息，给出最终回答。"),
            ])
            raw = response.content
            # ★ 深度思考：解析 <think>...</think> 标签
            reasoning = ""
            final = raw
            think_match = re.search(r"<think>(.*?)</think>", raw, re.DOTALL)
            if think_match:
                reasoning = think_match.group(1).strip()
                final = raw[think_match.end():].strip()
            # 部分模型 reasoning 在独立字段
            if not reasoning and hasattr(response, "reasoning_content") and response.reasoning_content:
                reasoning = response.reasoning_content

            logger.info(
                f"Supervisor 汇总完成（mode={mode}, deep_think={deep_think}, "
                f"smart_search={smart_search}），共 {len(worker_results)} 个 Worker 结果"
            )
            result = {
                "phase": "summary",
                "next_workers": [],
                "final_answer": final,
                "messages": [AIMessage(content=final)],
            }
            if reasoning:
                result["reasoning"] = reasoning
            return result
        except Exception as e:
            logger.error(f"Supervisor 汇总 LLM 调用失败: {e}")
            final = summary  # 降级：直接拼接 Worker 结果
            return {
                "phase": "summary",
                "next_workers": [],
                "final_answer": final,
                "messages": [AIMessage(content=final)],
            }

    # ── 新请求重置：清空 Checkpointer 恢复的旧中间状态 ──
    # Checkpointer 会恢复同一 thread 的全部字段（包括 phase="summary"、
    # worker_results、final_answer），不重置的话会命中 summary 分支
    # 把上一次的 Worker 结果重新汇总出来！
    _RESET = {
        "worker_results": {},     # merge_results reducer 收到空字典会清空
        "final_answer": "",
    }

    # 首轮：意图分类
    user_msg = _last_user_message(state)
    image = state.get("image")

    # ★ 识图模式：有图片时跳过 Worker 派发，直接进入汇总阶段用 vision 模型分析
    if image:
        logger.info(f"检测到图片，进入识图汇总阶段，用户消息: {user_msg[:30]}")
        return {**_RESET, "phase": "summary", "next_workers": []}

    # ★ 问候/闲聊 → 直接回答，不派发 Worker
    if _is_greeting(user_msg):
        direct = _greeting_response(user_msg)
        logger.info(f"问候语直接回答: {user_msg[:30]}")
        return {
            **_RESET,
            "phase": "routing",
            "next_workers": [],
            "final_answer": direct,
            "messages": [AIMessage(content=direct)],
        }

    # ★ 天气查询 → 调用高德天气 API，直接返回
    if is_weather_query(user_msg):
        logger.info(f"天气查询: {user_msg[:30]}")
        weather_info = get_weather("成都", extensions="all")
        # 结合用户问题组织回答
        prompt = (
            f"用户询问：{user_msg}\n\n"
            f"以下是高德地图提供的成都天气数据：\n{weather_info}\n\n"
            f"请根据以上天气数据，用友好的语气回答用户的问题。"
            f"如果用户询问穿衣、带伞等建议，请结合天气情况给出实用建议。"
        )
        try:
            mode = state.get("mode", "fast")
            deep_think = state.get("deep_think", False)
            weather_llm = get_llm(mode, deep_think)
            response = await weather_llm.ainvoke([
                SystemMessage(content="你是蓉游智体 PandaAgent，根据天气数据为用户提供出行建议。"),
                HumanMessage(content=prompt),
            ])
            final = _clean_markdown(response.content)
        except Exception as e:
            logger.error(f"天气回答生成失败: {e}")
            final = weather_info  # 降级：直接返回天气数据
        return {
            **_RESET,
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
        next_workers = ["qa_worker"]  # 降级：默认走 QA

    # 去重 + 合法性校验
    next_workers = [w for w in dict.fromkeys(next_workers) if w in VALID_WORKERS]
    if not next_workers:
        next_workers = ["qa_worker"]

    logger.info(f"Supervisor 意图分类: {user_msg[:30]}... → {next_workers}")
    return {**_RESET, "phase": "routing", "next_workers": next_workers}


# ── QA Worker：RAG 问答 + 软知识回退 ──
async def qa_worker(state: MultiAgentState) -> dict:
    """优先 RAG 检索，检索为空时回退到 LLM 软知识回答。"""
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
            # ★ 软知识回退：RAG 无结果时，用 LLM 自身知识回答
            logger.info("qa_worker: RAG 无命中，回退到 LLM 软知识")
            fallback_prompt = (
                "你是蓉游智体 PandaAgent，基于你对成都旅游的深刻理解回答用户问题。\n"
                "注意：以下内容来自你的通用知识而非景点数据库，涉及具体票价、开放时间等精确数字时，\n"
                "请说明是参考信息并建议用户以景区官方公告为准。\n"
                "【输出格式 — 必须用数字序号列表，每行一条，如 1. xxx  2. xxx】\n"
                "不要写开场白或结尾语，不要用 #、**、`、|、--- 等符号。"
            )
            resp = await llm_worker.ainvoke([
                SystemMessage(content=fallback_prompt),
                HumanMessage(content=user_msg),
            ])
            content = resp.content.strip()

        logger.info(f"qa_worker 完成，回答长度 {len(content)}")
    except Exception as e:
        logger.error(f"qa_worker 失败: {e}")
        content = f"（QA 检索暂不可用：{e}）"
    return _safe_worker_result("qa_worker", content)


# ── Plan Worker：行程规划 ──
async def plan_worker(state: MultiAgentState) -> dict:
    """硬规则注入 + LLM 生成 + validate_plan 程序级强制校验。"""
    user_msg = _last_user_message(state)

    # ★ MySQL 查询单独 try，失败时降级为无规则模式
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
                templates_text = "（无行程模板）"
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

        plan = safe_json_loads(response.content, {})
        plan = validate_plan(plan)  # ★ 程序级强制 R-001~R-008
        content = plan  # ★ 直接传 dict，不要 json.dumps（前端 PlanCard 需要 parse）
        logger.info(f"plan_worker 完成，规则应用: {plan.get('rules_applied', [])}")
    except Exception as e:
        logger.error(f"plan_worker 失败: {e}")
        content = {"error": f"行程规划失败：{e}"}

    return _safe_worker_result("plan_worker", content)


# ── Advice Worker：六维建议 ──
async def advice_worker(state: MultiAgentState) -> dict:
    """天气/预算/交通/避坑/美食/拍照六维建议。"""
    user_msg = _last_user_message(state)

    # ★ MySQL 查询单独 try，失败时降级为无规则模式，不阻断建议生成
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
        logger.info("advice_worker 完成")
    except Exception as e:
        logger.error(f"advice_worker 失败: {e}")
        content = f"（建议生成暂不可用：{e}）"

    return _safe_worker_result("advice_worker", content)


# ── Nearby Worker：周边推荐 ──
async def nearby_worker(state: MultiAgentState) -> dict:
    """LLM 识别景点 → MySQL 查坐标 → Bounding Box 预过滤 → Haversine 精算。"""
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
            # 查目标景点坐标
            target = conn.execute(
                text("SELECT longitude, latitude FROM spots WHERE spot_name=:name"),
                {"name": target_spot},
            ).fetchone()
            if not target:
                return _safe_worker_result("nearby_worker", f"未找到景点：{target_spot}")

            lon, lat = float(target[0]), float(target[1])

            # ★ Bounding Box 预过滤（1°≈111km，减少 Haversine 计算量）
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
        nearby = nearby[:10]

        content = nearby  # ★ 直接传 list，不要 json.dumps（前端 NearbyList 直接解析）
        logger.info(f"nearby_worker 完成，{target_spot} 周边 {radius_km}km 内 {len(nearby)} 个景点")
    except Exception as e:
        logger.error(f"nearby_worker 失败: {e}")
        content = {"error": f"周边推荐失败：{e}"}

    return _safe_worker_result("nearby_worker", content)
