# 🏯 蓉游智体 · Chengdu Travel AI Agent

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python)
![Node](https://img.shields.io/badge/Node.js-19+-green?logo=node.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-1C3F94?logo=langchain)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)
![Milvus](https://img.shields.io/badge/Milvus-Lite-00A0FF?logo=milvus)
![MySQL](https://img.shields.io/badge/MySQL-8-4479A1?logo=mysql)
![License](https://img.shields.io/badge/License-MIT-yellow)

> 一个基于 **多智能体 + RAG** 的成都旅游问答与行程规划助手，LangGraph 驱动 Supervisor 并行调度 4 个 Worker，LlamaIndex + Milvus 提供双轨制检索增强，53 条硬规则保障行程合理性。

---

## 🧭 项目定位

这是一个**面向真实用户场景**的 AI Agent 实战项目，不是 Demo Toy：

- 🏛️ **覆盖 1554 个成都景点**、80+ 美食、250+ 避坑规则，全量种子数据入库
- 🚇 **19 万条景点间通勤矩阵**（高德地图 API 批量计算），行程规划精确到分钟
- 🛡️ **三层防幻觉**：硬事实强制来自检索内容 + 53 条硬规则 + validate_plan 程序级校验
- 🔄 **多意图并行**：用户问"熊猫基地怎么去 + 附近有什么吃的"，Supervisor 同时派发 QA + Nearby + Advice 三个 Worker
- 💬 **流式 SSE 输出** + 引用标注，前端直接渲染 Markdown

---

## 🏗️ 系统架构

```mermaid
graph TD
    User("👤 用户") -->|SSE / HTTP| Frontend("🖥️ React 前端<br/>(Vite + Semi UI)")
    Frontend -->|POST /chat| API("⚡ FastAPI 路由<br/>chat_routes / spot_routes / health")
    API --> Graph("🧠 LangGraph StateGraph<br/>Supervisor + Send API")
    
    subgraph Agent["多智能体层 · LangGraph"]
        Supervisor("🎯 Supervisor<br/>意图分类 / 并行路由")
        QA("🔍 QA Worker<br/>RAG 双轨制问答")
        Plan("📅 Plan Worker<br/>硬规则 + 行程生成")
        Advice("💡 Advice Worker<br/>六维避坑建议")
        Nearby("📍 Nearby Worker<br/>Haversine 周边")
    end
    
    Supervisor -->|Send 并行| QA & Plan & Advice & Nearby
    QA & Plan & Advice & Nearby -->|汇总| Supervisor
    
    subgraph RAG["检索增强层 · LlamaIndex + Milvus"]
        QueryEngine("QueryEngine<br/>Top-K = 5")
        Embed("BAAI/bge-large-zh-v1.5<br/>1024 维嵌入")
        Rerank("bge-reranker-large<br/>重排")
        VectorStore("Milvus Lite<br/>chengdu_spots 集合")
    end
    
    subgraph Data["数据层"]
        MySQL("🗄️ MySQL 8<br/>景点 / 美食 / 通勤")
        Seeds("📄 CSV Seeds<br/>1554 景点 / 19w 通勤")
        Augmented("📊 RAG Augmented<br/>query_variants 12600+ 条")
    end
    
    API --> MySQL
    QA --> QueryEngine
    QueryEngine --> VectorStore
    VectorStore --> Embed
    QueryEngine --> Rerank

    style Agent fill:#1C3F94,color:#fff
    style RAG fill:#00A0FF,color:#fff
    style Data fill:#4479A1,color:#fff
```

---

## 🧰 技术栈

### ⚡ 后端框架

| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.115 | ASGI Web 框架，类型安全路由 |
| Uvicorn | 0.30 | 异步 ASGI 服务器 |
| Pydantic | 2.9 | Settings + 数据校验 |
| SQLAlchemy | 2.0 | ORM 与 MySQL 连接 |

### 🤖 AI Agent 核心

| 技术 | 版本 | 用途 |
|------|------|------|
| LangGraph | 0.2 | StateGraph + Send API 并行调度 |
| LangChain | 0.3 | LLM 抽象 / Runnable / 回调 |
| LangSmith | — | 全链路 Trace 可观测性 |
| DeepSeek | V4-Pro / Flash | LLM 推理（多模型切换） |

### 📚 RAG 检索增强

| 技术 | 版本 | 用途 |
|------|------|------|
| LlamaIndex | — | QueryEngine / Retriever |
| Milvus Lite | 3.0 | 本地向量存储（零服务端依赖） |
| BAAI/bge-large-zh | 1.5 | 1024 维中文嵌入模型 |
| bge-reranker-large | — | 重排提升召回精度 |
| BM25 (rank_bm25) | — | 稀疏检索 + 向量融合 |

### 🖥️ 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19 | UI 框架 |
| Vite | 8 | 构建工具 |
| Semi UI | 2.103 | 组件库 |
| SSE.js | 2.8 | 流式响应 |

### 💾 数据 / 工具

| 技术 | 版本 | 用途 |
|------|------|------|
| MySQL | 8.0 | 景点 / 美食 / 通勤矩阵持久化 |
| Redis | 5 | Checkpointer 备选后端（当前未启用，默认 SqliteSaver） |
| SqliteSaver | — | LangGraph 跨重启 Checkpointer |
| Loguru | 0.7 | 结构化日志 |

---

## ⚙️ 配置中心（Pydantic Settings）

`config.py` 用 `BaseSettings` 实现类型安全的单例配置，`.env` 文件注入 + 环境变量覆盖。全项目 `from app.config import settings` 统一访问。

| 分组 | 关键配置 | 默认值 | 说明 |
|------|---------|--------|------|
| **LLM** | `DEEPSEEK_MODEL` | `deepseek-chat` | 快速模式 |
| | `DEEPSEEK_MODEL_PRO` | `deepseek-v4-pro` | 专家模式 |
| | `DEEPSEEK_MODEL_REASONER` | `deepseek-reasoner` | 深度思考（带 `<think>`） |
| | `DEEPSEEK_MODEL_VISION` | `deepseek-v4-flash-vision-exp` | 识图模式 |
| **高德** | `AMAP_API_KEY` | `""` | 天气 + 通勤矩阵计算 |
| **MySQL** | `MYSQL_DB` | `chengdu_travel` | 9 张表 |
| **Milvus** | `MILVUS_DB_PATH` | `127.0.0.1:19530` | Standalone 地址，`.db` 后缀自动切 Lite |
| | `MILVUS_COLLECTION_SPOTS` | `chengdu_spots` | RAG 集合 |
| | `MILVUS_COLLECTION_LTM` | `user_ltm_v1` | LTM 用户画像集合 |
| | `MILVUS_DIM` | `1024` | BGE 向量维度 |
| **LTM** | `LTM_DEDUP_THRESHOLD` | `0.92` | 语义去重阈值 |
| **Embedding** | `EMBED_MODEL_NAME` | `BAAI/bge-large-zh-v1.5` | 中文嵌入 |
| | `RERANKER_MODEL_NAME` | `BAAI/bge-reranker-large` | 重排器 |
| **Checkpoint** | `CHECKPOINT_BACKEND` | `sqlite` | 可选 memory/redis/postgres |
| **LangSmith** | `LANGCHAIN_TRACING_V2` | `true` | 全链路追踪开关 |

**派生属性**（`@property`）：
- `mysql_url` → `mysql+pymysql://user:pass@host:port/db?charset=utf8mb4`
- `redis_url` → `redis://[:pass]@host:port/db`（有密码时带 `:` 前缀）
- `is_milvus_lite` → `MILVUS_DB_PATH.endswith(".db")`
- `milvus_uri` → Lite 返回文件路径，Standalone 返回 `http://host:port`

---

## ✨ 核心特性

### 🎯 1. Supervisor 多意图并行路由

用户的模糊查询（如"熊猫基地怎么去 + 附近有什么吃的"）被 Supervisor 分类后，通过 LangGraph `Send` API **并行派发**到多个 Worker，结果自动汇总：

```mermaid
graph LR
    U("熊猫基地<br/>怎么去+附近吃的") --> S("Supervisor<br/>意图分类")
    S -->|Send 并行| Q("QA Worker<br/>怎么去") & N("Nearby Worker<br/>附近景点") & A("Advice Worker<br/>附近美食")
    Q & N & A --> R("Supervisor<br/>汇总输出")
```

- Supervisor 用 LLM 做意图分类，输出 JSON `{"next_workers": ["qa_worker", "nearby_worker", ...]}`
- 4 个 Worker 并行执行，`worker_results` 字段用自定义 reducer 自动合并
- Worker 完成后自动 join 回 Supervisor，由 `SUPERVISOR_SUMMARY_PROMPT` 做最终整合

### 🔍 2. RAG 双轨制 Prompt + 混合检索

**检索链路**：用户 Query → 向量 Top10 + BM25 Top10 → QueryFusionRetriever 融合 → BGE Reranker 重排 Top3 → 动态 Prompt → LLM 生成

```
Query → VectorIndexRetriever (BGE 1024维 Top10)
      → BM25Retriever (单字 token_pattern 中文 Top10)
      → QueryFusionRetriever (simple 融合 Top20)
      → SentenceTransformerRerank (bge-reranker-large Top3)
      → KeywordBoostPostprocessor (source_name 重叠加权 + travel_tips ×1.3)
      → DynamicTextQAPrompt (双轨制 + 7维度组)
      → DeepSeek LLM
```

**硬事实轨道**（不可编造）：
> 门票价格、开放时间、地址、经纬度、通勤时间、评分、人均消费、景点等级 → 必须使用检索内容，检索中没有则回答"暂无相关信息"

**软知识轨道**（按关键词激活 G1~G7）：
| 组 | 维度 | 触发关键词示例 |
|---|------|---------------|
| G1 | 文化介绍 | 介绍、历史、文化、典故、故事、特产 |
| G2 | 游览攻略 | 怎么玩、攻略、逛、拍照、出片、机位 |
| G3 | 季节天气 | 几月、季节、天气、雨天、什么时候去 |
| G4 | 人群特殊 | 老人、小孩、亲子、情侣、轮椅、宠物 |
| G5 | 交通出行 | 怎么去、交通、地铁、预约、门票怎么买 |
| G6 | 周边串联 | 附近、周边、怎么串、一日游、吃什么 |
| G7 | 装备准备 | 带什么、穿什么、注意事项、安全、装备 |

- `build_qa_prompt(query, context)` 根据 `detect_groups()` 匹配关键词，动态拼接 `QA_BASE_PROMPT` + 相关维度组
- `DynamicTextQAPrompt` 继承 LlamaIndex `PromptTemplate`，重写 `format()` 实现运行时动态 Prompt

### 🛡️ 3. 三层硬规则保障

| 层级 | 机制 | 示例 |
|------|------|------|
| **程序级** | `validate_plan()` Python 硬编码 8 条规则 | R-001: 熊猫基地强制 Day1 上午 08:00-12:00，原安排自动移至下午 |
| **Prompt 级** | 53 条规则注入 `PLAN_PROMPT` 的 `{hard_rules}` 占位 | 武侯祠+锦里必须同半天、都江堰+青城山必须同一天、Leshan 大佛排除 ≤3 日行程 |
| **校验级** | Plan Worker 生成后自动调 `validate_plan()` 修正 | 违规记录到 `plan["rules_applied"]` 供调试 |

**程序级 8 条规则**（见 [utils.py](backend/app/agents/utils.py)）：
- R-001 熊猫基地 → Day1 上午（强制覆盖，原安排保留到下午）
- R-002 都江堰+青城山不与市区混排
- R-003 武侯祠+锦里同半天
- R-004 杜甫草堂+金沙同半天
- R-005 周一排除金沙/川博
- R-006 每日 ≤3 景点
- R-007 每日通勤 ≤180 分钟
- R-008 亲子/老人团排除西岭雪山

### 🚇 4. 通勤矩阵 + Haversine 周边

- **190,158 条**景点对的双向通勤时间/距离，覆盖全部 1554 个景点
- 由高德地图 distance 批量 API 计算（100 点/请求，两阶段：区域内全精确 + 跨区域 Top100 热门）
- Nearby Worker 用 **Haversine 公式**（地球半径 6371km）计算球面距离，按半径过滤周边景点（市区 3km / 默认 5km / 郊区 10km）
- 行程规划时 `transit_matrix` 作为 `PLAN_PROMPT` 的 `{transit_matrix}` 占位注入，确保 LLM 生成的通勤时间真实可查

### 🧠 5. 长期用户画像记忆（LTM）

**MySQL 硬槽位** `user_profiles` 表（9 个字段）：
| 字段 | 类型 | 说明 |
|------|------|------|
| `group_type` | Enum | solo / couple / family / friends / business / senior |
| `budget_level` | Enum | budget / standard / comfort / luxury |
| `pace` | Enum | relaxed / moderate / packed |
| `allergies_json` | JSON | 忌口/黑名单 |
| `must_include_json` | JSON | 必去景点 |
| `must_exclude_json` | JSON | 黑名单景点 |
| `notes` | Text | 自由备注 |
| `ltm_chunk_count` | Integer | 累计 LTM 提取次数 |
| `ltm_last_extract_at` | DateTime | 最近一次提取时间 |

**Milvus 向量记忆** `user_ltm_v1` 集合：
- 用户偏好（如"喜欢小众景点""拍照好看优先"）以向量形式存储
- 跨会话持久化，语义去重阈值 0.92
- LTM 提取失败时写入 `dlq`（DeadLetter 死信队列），支持异步重试

---

## 🔌 API 接口协议

### `GET /health` — 全链路健康检查

逐项探测 MySQL / Milvus / LLM API Key / Checkpointer / Redis，前端可据此做连接状态指示灯。

```json
{
  "status": "ok",
  "mysql": "ok",
  "milvus": "ok",
  "llm": "ok",
  "checkpoint": "ok (sqlite)",
  "redis": "skipped (optional)",
  "config_loaded": true,
  "llm_model": "deepseek-chat",
  "rag_engine": "llamaindex",
  "milvus_dim": 1024,
  "checkpoint_backend": "sqlite",
  "mysql_db": "chengdu_travel"
}
```

### `GET /api/spots` — 景点搜索

支持关键词模糊匹配（spot_name / address）、级别过滤（5A/4A/3A）、区域过滤（成华区/武侯区...）、分页（limit 默认 20，最大 200），按 rating DESC + spot_level DESC 排序。

| 参数 | 类型 | 说明 |
|------|------|------|
| `keyword` | query | 模糊搜索景点名或地址 |
| `spot_level` | query | 级别过滤 |
| `area_tag` | query | 区域过滤 |
| `limit` | query | 每页数量，默认 20 |
| `offset` | query | 偏移量 |

### `GET /api/spots/{spot_id}` — 景点详情

返回完整字段，含 `description` / `travel_tips` / `cultural_context` 三个长文本（RAG 向量化源）和 `avg_visit_hours`。

### `POST /api/chat` — SSE 流式对话

唯一的 Agent 入口。请求体：

| 字段 | 类型 | 说明 |
|------|------|------|
| `message` | string | 用户问题 |
| `session_id` | string | 会话 ID（多会话隔离） |
| `mode` | enum | `fast` / `expert` / `vision` |
| `deep_think` | bool | 是否开启深度思考（reasoner 模型） |
| `smart_search` | bool | 是否联网搜索（DuckDuckGo HTML） |
| `image` | string | 图片 base64 dataURL（vision 模式） |

---

## 📡 SSE 流式事件协议

`/api/chat` 返回 `text/event-stream`，4 种事件类型，前端 `sse.js` 消费：

| 事件 | 触发时机 | data 示例 |
|------|---------|-----------|
| `token` | LLM 流式输出每个 token | `{"text": "今天"}` |
| `reasoning` | DeepSeek reasoner 深度思考过程 | `{"text": "用户问的是...所以应该..."}` |
| `structure_ready` | Worker 完成，结构化卡片先行推送 | `{"type": "plan_card", "payload": {...}}` |
| `end` | Supervisor 最终汇总完成 | `{"final_answer": "...", "session_id": "..."}` |

**Worker → 卡片类型映射**：

| Worker | 卡片类型 | 前端组件 |
|--------|---------|---------|
| `qa_worker` | `qa_card` | QACard |
| `plan_worker` | `plan_card` | PlanCard |
| `advice_worker` | `advice_panel` | AdvicePanel |
| `nearby_worker` | `nearby_list` | NearbyList |

**关键实现细节**：
- `stream_events` 只用 **一次**，避免 Checkpointer 恢复导致 Worker 跳过
- 每个请求生成唯一 `thread_id = {session_id}_{timestamp}_{uuid8}`，跨请求永不串状态
- `initial_state` 手动重置 `phase/worker_results/final_answer`，覆盖 Checkpointer 恢复的旧中间状态
- `_clean_markdown()` 轻量清洗：保留 ## 标题、列表、表格、引用块，去除 `**加粗**`、`代码标记`、`--- 分隔线`
- `structure_ready` 去重：`emitted_workers` 集合确保同一 Worker 只推一次卡片

---

## 🧠 LangGraph State Schema

`MultiAgentState`（TypedDict + Annotated reducer）定义了多智能体共享状态的完整字段：

| 字段 | 类型 | Reducer | 说明 |
|------|------|---------|------|
| `messages` | list | `add_messages` | 聊天历史（LangGraph 一等字段，随 Checkpointer 自动持久化） |
| `next_workers` | list | — | Supervisor 意图分类结果 |
| `worker_results` | dict | `merge_results` | 并行 Worker 输出，right 覆盖同名 key；right 为空时清空 |
| `final_answer` | str | — | Supervisor 第二轮汇总结果 |
| `reasoning` | str | — | 深度思考过程 |
| `phase` | Literal | — | `routing` / `summary` 两阶段标识 |
| `mode` | Literal | — | `fast` / `expert` / `vision` |
| `deep_think` | bool | — | 深度思考开关 |
| `smart_search` | bool | — | 联网搜索开关 |
| `image` | str | — | 图片 base64 |
| `user_id` | str | — | 用户标识 |
| `session_id` | str | — | 会话 ID |
| `debug_info` | dict | `merge_debug_info` | 各节点耗时、token 数，逐层 deep merge |

**自定义 reducer 逻辑**：
- `merge_results`：right 为空字典时 → 完全替换 left（routing 阶段清空旧中间状态）；正常 Worker 输出时 → 合并
- `merge_debug_info`：递归 deep merge，不覆盖已有节点的统计

---

## 🧩 LLM 多模型工厂

`llm_client.py` 预创建 6 个 ChatOpenAI 实例，`get_llm(mode, deep_think)` 按前端模式 + 深度思考开关选择：

| 实例 | 模型 | 温度 | Streaming | 用途 |
|------|------|------|-----------|------|
| `llm` | deepseek-chat | 0.3 | ✅ | 快速模式 Supervisor / QA Worker |
| `llm_pro` | deepseek-v4-pro | 0.7 | ✅ | 专家模式 |
| `llm_reasoner` | deepseek-reasoner | 0.7 | ✅ | 深度思考，输出带 `<think>...</think>` |
| `llm_vision` | deepseek-v4-flash-vision-exp | 0.3 | ✅ | 识图模式 |
| `llm_json` | deepseek-chat | 0.1 | ❌ | Supervisor 意图分类（non-streaming + JSON Mode） |
| `llm_worker` | deepseek-chat | 0.3 | ❌ | Advice/Plan Worker（non-streaming，不泄漏流式响应） |

**选择优先级**：`deep_think` > `mode`（reasoner 覆盖 expert/fast）

**关键约束**：`llm_json` 和 `llm_worker` 必须 non-streaming —— 否则 Supervisor 的 JSON 输出或 Worker 的卡片内容会泄漏到聊天流式响应中。

---

## 🎭 Supervisor 两轮职责 + 5 条特殊路径

Supervisor 不是单一节点，而是**同一节点承担两轮职责**，通过 `state["phase"]` 和 `worker_results` 是否为空自动切换：

```
首轮（phase="routing" 或 worker_results 为空）
  ├─ 识图模式（有 image）→ 跳过 Worker，直接进入 summary 用 vision 模型
  ├─ 问候语 → 直接回答，不派发 Worker
  ├─ 天气查询 → 调高德天气 API + LLM 润色
  └─ 正常意图分类 → llm_json 输出 JSON → Send 并行派发 Worker

次轮（phase="summary" 或 worker_results 非空）
  ├─ 识图模式 → vision 模型多模态分析
  ├─ 无 Worker 结果（如问候被直接处理）→ 用 LLM 软知识回答
  └─ 正常汇总 → smart_search 联网追加 → SUPERVISOR_SUMMARY_PROMPT 整合 → <think> 解析
```

**深度思考 `<think>` 标签解析**：reasoner 模型返回的 raw 输出含 `<think>思考内容</think>最终回答`，Supervisor 用正则提取中间的 reasoning 字段和最终的 final_answer，分别推 SSE 事件。部分模型 reasoning 在 `response.reasoning_content` 独立字段，做了双路径兼容。

**降级策略**：Supervisor 汇总 LLM 调用失败时，直接拼接 Worker 原始结果作为 final_answer（不丢失信息）。

**意图分类降级**：JSON 解析失败或 Worker 列表为空时，默认走 `qa_worker`。

---

## 👷 四个 Worker 实现细节

### QA Worker — RAG + 软知识回退

- 优先 `build_query_engine().aquery(user_msg)` 调用 RAG
- 检索为空（"知识库中暂无" / "empty response"）→ **回退到 LLM 软知识回答**
- 软知识回退时强制输出数字序号列表（禁止 #、**、`、|、--- 等符号），说明是参考信息

### Plan Worker — 硬规则注入 + 程序级校验

- **SQL 动态查询**：MySQL 查询 hard_rules（按 priority ASC 排序）+ transit_matrix（same_region=1 LIMIT 20）+ itinerary_templates
- 三项数据作为 `{hard_rules}` / `{transit_matrix}` / `{templates}` 占位注入 `PLAN_PROMPT`
- LLM 输出 JSON 后，**立即调 `validate_plan()` 做程序级校验**
- 违规记录到 `plan["rules_applied"]`（如 `R-002(violated:day1都江堰与市区混排)`）
- MySQL 查询失败降级为"无规则/无通勤/无模板"模式，不阻断生成

### Advice Worker — 六维建议 + 避坑规则注入

- 从 MySQL 查 avoid_rules（250+ 条），注入 `ADVICE_PROMPT` 的 `{avoid_rules}` 占位
- 按 6 个维度组织回答：🌤 天气季节 / 💰 预算参考 / 🚇 交通出行 / ⚠️ 避坑提醒 / 🍜 美食推荐 / 📸 拍照攻略
- 输出禁止表格、**加粗**、代码块、--- 分隔线

### Nearby Worker — Haversine 球面距离 + 动态半径

- Supervisor 先调 LLM 做 **景点名识别 + 半径决策**（输出 JSON `{"spot_name": "宽窄巷子", "radius_km": 5}`）
- 半径策略：市区景点 3km / 默认 5km / 郊区（都江堰/青城山）10km
- 从 MySQL 查目标景点经纬度 → Haversine 公式算球面距离 → 过滤半径内景点
- Haversine 参数：地球半径 R = 6371.0 km

---

## 🔧 工具层

| 工具 | 实现 | 降级策略 |
|------|------|---------|
| **高德天气** | `httpx.get` → `restapi.amap.com/v3/weather/weatherInfo`，extensions=all 返回 3 天预报 | AMAP_API_KEY 未配置时直接返回"暂不可用" |
| **DuckDuckGo 联网搜索** | `requests.post` → `html.duckduckgo.com/html/`，正则提取 `result__a` 链接 + `result__snippet` 摘要 | 国内网络不稳定，失败返回空字符串，Agent 退化为纯 RAG |
| **天气关键词判断** | 23 个关键词（天气/气温/下雨/带伞/防晒...），命中则跳过 Worker 直接调天气 API | — |

**Supervisor 智能搜索**：`smart_search=True` 时，Worker 结果汇总后调 `web_search(user_msg)`，结果追加到 `【联网搜索结果】` 段落，再一起送入 SUMMARY_PROMPT。

---

## 🛡️ validate_plan 8 条硬规则程序级实现

`utils.py` 的 `validate_plan(plan)` 深拷贝入参后逐条检查，结果写入 `plan["rules_applied"]`。与 Prompt 注入形成**双保险**——LLM 可能漏看 Prompt 里的规则，但 Python 代码不会。

| 编号 | 规则 | 类型 | 实现要点 |
|------|------|------|---------|
| **R-001** | 熊猫基地必须 Day1 7:30-12:00 | 🔴 **强制覆盖**（最后执行） | 原安排挪到下午或记录到 `original_spot` 字段，保留用户意图 |
| R-002 | 都江堰+青城山必须同天，不与市区混排 | 🟡 检测 | 遍历每天 slots，关键词匹配"都江堰/青城山"+"宽窄/锦里/春熙/武侯祠/杜甫草堂" |
| R-003 | 武侯祠+锦里必须同半天（一墙之隔） | 🟡 检测 | 检查 morning/afternoon 是否同时包含两个景点 |
| R-004 | 杜甫草堂+金沙遗址同半天（车程 15 分钟） | 🟡 检测 | 同上 |
| R-005 | 金沙/川博周一闭馆 | 🟡 检测 | `weekday() == 0` 时排除"金沙/四川博物院/川博" |
| R-006 | 每日景点 ≤ 3 个 | 🟡 检测 | 统计非 reserved_keys 的 slot 数 |
| R-007 | 每日通勤 ≤ 180 分钟 | 🟡 检测 | `transit_minutes > 180` |
| R-008 | 亲子/老人团避免西岭雪山（3000m+） | 🟡 检测 | `group_type in ("亲子","老人","家庭")` + "西岭雪山" |

**执行顺序关键**：R-001 放在最后执行——它是**强制覆盖型**规则，会修改 plan 结构；其他 7 条是**检测型**，只记录不修改。如果先执行 R-001，它插入熊猫基地后，后面的检测规则会误报新插入内容。

---

## 🔴 Checkpointer 工厂模式

`get_checkpointer_async()` 按 `CHECKPOINT_BACKEND` 环境变量一行切换后端：

| 后端 | 适用场景 | 特点 |
|------|---------|------|
| **SqliteSaver**（默认） | 本地开发 / 零服务端 | WAL 模式 + 30s timeout 避免 "database is locked" |
| **PostgresSaver** | 生产级 | ACID + 行级锁并发 + `saver.setup()` 自动建表 |
| **RedisSaver** | 高并发 | Redis Stack（RedisJSON + RediSearch） |
| **MemorySaver** | 调试 | 不跨重启，进程退出即丢失 |

设计要点：异步用 `@asynccontextmanager` 做资源生命周期管理（Postgres 需 `AsyncConnectionPool`，Redis 需 `aclose()`）。

---

## 🤯 LlamaIndex Monkey-Patch 三部曲

DeepSeek API 完全兼容 OpenAI Chat API，但 LlamaIndex 硬编码了 OpenAI 模型列表且默认用 legacy `/completions` 端点。`_ensure_settings()` 做了三处 patch：

| Patch | 目标 | 做法 |
|-------|------|------|
| **模型注册表** | `llama_index.llms.openai.utils.ALL_AVAILABLE_MODELS` | 注入 deepseek-chat / V4-Pro / reasoner / vision，context_window 设 131072 |
| **Tokenizer 映射** | `tiktoken.model.MODEL_TO_ENCODING` | 映射到 `cl100k_base`（DeepSeek 同款） |
| **API 端点** | `OpenAI._complete` / `_acomplete` | 覆盖为 `chat.completions.create()`（DeepSeek 不支持 legacy completions） |

---

## 🎨 BGE Embedding 细节

BGE v1.5 官方规定：**Query 路径必须加 instruction 前缀**，否则召回率下降 10%+。

| 路径 | 前缀 | L2 归一化 |
|------|------|----------|
| Query | `"为这个句子生成表示以用于检索相关文章："` + 用户问题 | ✅ |
| Document | 无，直接编码 | ✅ |

LlamaIndex 从 Milvus 全量加载节点建 BM25 索引时，把 `source_name`（景点名）拼入文本头部，增强名称匹配权重。BM25 用单字 `token_pattern=r"[\u4e00-\u9fa5]|[a-zA-Z0-9]+"` 避免中文分词后查询无法对齐。

---

## 🔍 RAG 混合检索完整链路

`build_query_engine()` 组装了一条 5 级流水线：

```
用户 Query
    │
    ├─→ VectorIndexRetriever（BGE 向量 Top10）──┐
    ├─→ BM25Retriever（关键词 Top10）──────────┤
    │                                          ↓
    │                              QueryFusionRetriever（mode=simple, reciprocal_rerank）
    │                                          │
    │                                          ↓ Top20
    │                              BGE Reranker（SentenceTransformerRerank）
    │                                          │
    │                                          ↓ Top3
    │                              KeywordBoostPostprocessor（自定义后处理）
    │                                          │
    │                              ┌───────────┴───────────┐
    │                              ↓                       ↓
    │                      source_name 重叠加权      travel_tips 块类型加权
    │                      score × (1 + 0.1 × overlap) × 1.5   score × 1.3
    │                              │
    │                              ↓
    │                       DynamicTextQAPrompt（双轨制 Prompt）
    │                              │
    └──────────────────────────────┴
                                   ↓
                            LLM 生成最终回答
```

**QueryFusionRetriever 参数**：`mode="simple"`（两种检索器等权融合）、`num_queries=1`（不做 Query Decomposition）、`similarity_top_k=20`

**KeywordBoostPostprocessor 逻辑**：
- `boost=1.5` 基础乘数
- `source_name` 与 query 有字符重叠 → `score × (1 + 0.1 × 重叠字数) × 1.5`
- `chunk_type == "travel_tips"`（含票价/开放时间等硬事实）→ 额外 `score × 1.3`

**Response Synthesizer**：`response_mode="compact"`，避免重复检索内容灌入 Prompt

---

## 🖥️ 前端交互流程

**会话管理**（localStorage 持久化）：
- 会话列表：`{id, title, messages[], createdAt, updatedAt}`
- 标题自动取首条用户消息前 20 字（图片会话取图片名）
- Sidebar 支持新建 / 选择 / 删除，删除当前自动切到第一个

**聊天模式**：

| 模式 | LLM | 说明 |
|------|-----|------|
| Fast | deepseek-chat | 快速回答 |
| Expert | deepseek-v4-pro | 专家级深度回答 |
| Vision | deepseek-v4-flash-vision-exp | 图片识图 |

**SSE 消费**（`sse.js` + POST）：
- 原生 `EventSource` 只支持 GET，前端用 `sse.js` 的 `EventSourcePolyfill` 实现 POST + SSE
- 4 个回调：`onToken`（增量渲染）/ `onReasoning`（深度思考展开）/ `onStructure`（结构化卡片先行）/ `onEnd`（最终收敛）
- 返回取消函数，切换会话 / 关闭页面前 abort

**Markdown 渲染约定**：后端 `_clean_markdown()` 清洗掉 `**加粗**`、`代码标记`、`--- 分隔线`，前端用 Semi UI 的 Typography 直接渲染剩余的标题/列表/表格/引用块。

**Vite SSE 代理**（`vite.config.js`）：前端 `/api/*` → `http://localhost:8000/*`，`proxyReq` 阶段注入 `X-Accel-Buffering: no` 禁用 Nginx 缓冲（SSE 必需，否则 Token 会攒一批才推到前端）。`allowedHosts: true` + `host: 0.0.0.0` 允许穿透工具访问。

---

## 📦 数据管道

**三个脚本完成从 CSV 种子到 RAG 索引**：

| 脚本 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `01_init_db_create_tables.py` | — | MySQL 9 张表 | spots / foods / food_shops / avoid_rules / hard_rules / transit_matrix / chat_sessions / user_profiles / dlq |
| `02_import_seeds.py` | `data/seeds/*.csv` | MySQL | 删除旧种子表再追加，重置自增主键；保留 chat_sessions / user_profiles / dlq 不被清空 |
| `03_build_rag_index.py` | `data/augmented/*.csv` | Milvus `chengdu_spots` 集合 + `query_variants` 12600+ 条 query 扩展 | BGE 1.5 向量化 → Milvus Lite 本地 DB |

**9 张 MySQL 表**：

| 表 | 说明 | 运行时 |
|----|------|--------|
| `spots` | 1554 景点（坐标/等级/票价/开放时间/描述/贴士/文化） | 每次查询 |
| `foods` | 80+ 美食 | Advice Worker |
| `food_shops` | 美食店铺 | Advice Worker |
| `avoid_rules` | 250+ 避坑规则 | Advice Worker |
| `hard_rules` | 53 条硬规则 | Plan Worker Prompt |
| `transit_matrix` | 190,158 通勤对 | Plan Worker Prompt |
| `chat_sessions` | 冷备归档（Checkpointer 热备） | 异步归档 |
| `user_profiles` | LTM 硬槽位（9 字段 Enum/JSON） | finalize_prompt 注入 |
| `dlq` | 死信队列（archive / ltm_extract / notify） | 异步重试 |

**联网搜索降级策略**：`web_search()` 基于 DuckDuckGo HTML 搜索，国内不稳定时失败返回空字符串，Agent 自动退化为纯本地 RAG 回答。

---

## 🗄️ 数据库表结构（9 张表）

### spots — 景点（1554 条）

| 字段 | 类型 | 说明 |
|------|------|------|
| `spot_id` | INT PK | 自增主键 |
| `spot_name` | VARCHAR(128) | 景点名称 |
| `spot_level` | VARCHAR(16) | 5A/4A/3A/- |
| `longitude` / `latitude` | DECIMAL(10,7) | 精确到 0.0000001 度（~1cm） |
| `rating` | DECIMAL(3,1) | 0-5 评分 |
| `ticket_price_min` | INT | 最低门票（元） |
| `opening_hours_json` | JSON | `{open: "08:00", close: "18:00"}` |
| `area_tag` | VARCHAR(32) | 所属区县（成华区/武侯区...） |
| `description` / `travel_tips` / `cultural_context` | TEXT | RAG 向量化三大长文本 |

**索引**：`idx_spots_name`（名称模糊搜索）、`idx_spots_area`（区域过滤）、`idx_spots_location(longitude, latitude)`（Haversine 半径查询）

### transit_matrix — 通勤矩阵（190,157 条）

| 字段 | 类型 | 说明 |
|------|------|------|
| `from_spot_id` / `to_spot_id` | INT | 景点 ID |
| `transit_mode` | ENUM | `driving` / `transit` / `walking` |
| `duration_min` | INT | 通勤分钟数 |
| `distance_km` | DECIMAL(8,2) | 公里数 |
| `same_region` | BOOLEAN | 是否同区域（Plan Worker 优先同区域景点） |

**约束**：`UNIQUE(from_spot_id, to_spot_id, transit_mode)` 避免重复计算；双向覆盖（A→B 和 B→A 各一条）

### hard_rules — 硬规则（53 条）

| 字段 | 类型 | 说明 |
|------|------|------|
| `rule_id` | VARCHAR(16) PK | R-001 ~ R-053 |
| `rule_content` | TEXT | 规则内容（注入 Prompt） |
| `priority` | INT | 数字越小越高，Plan Worker 按 ASC 排序注入 |

### user_profiles — LTM 硬槽位

| 字段 | 类型 | Enum 取值 |
|------|------|----------|
| `group_type` | ENUM | solo / couple / family / friends / business / senior |
| `budget_level` | ENUM | budget / standard / comfort / luxury |
| `pace` | ENUM | relaxed / moderate / packed |
| `allergies_json` / `must_include_json` / `must_exclude_json` | JSON | 忌口 / 必去 / 黑名单 |
| `ltm_chunk_count` | INT | 累计 LTM 提取次数（防频繁覆盖） |

### dlq — 死信队列

| 字段 | 类型 | 说明 |
|------|------|------|
| `phase` | ENUM | archive / ltm_extract / notify |
| `payload_json` | JSON | 原 state / profile 快照（支持手动重试） |
| `retry_count` | INT | 已重试次数 |
| `next_retry_at` | DATETIME | 下次重试时间 |

**索引**：`idx_dlq_phase_retry(phase, next_retry_at)` 支持定时扫描待重试死信

---

## 🧩 前端组件细节

### PlanCard — 行程规划卡片

- `parsePlan()` 兼容两种 payload：dict（`{days, title, budget, rules_applied}`）和数组
- `renderSpot()` 渲染 `{spot_name, time, desc}` → `"⏰ 08:00-12:00 · 熊猫基地 · 上午最活跃"`
- 每天分 ☀️ 上午 / 🌤️ 下午 / 🌙 晚上 三个 slot，时间线布局
- 预算 Tag（蓝色）+ 硬规则 Tag（绿色，显示规则条数）
- `rules_applied` 数组直接展示 LLM 触发的规则违规/强制记录

### QACard — 知识库问答卡片

- 接收 `qa_worker` 的 `structure_ready` payload
- `parseQA()` 兼容 `{answer, citations}` 和 `{summary, sources}` 两种字段名
- 引用出处用 `CitationTag` 组件展示（标签化显示来源景点名）
- `whiteSpace: 'pre-wrap'` 保留后端 `_clean_markdown()` 清洗后的换行

### ChatInput — 输入框

- 三模式切换：Fast / Expert / Vision
- Vision 模式支持图片上传（`type="file"` → base64 dataURL）
- `smart_search` 开关（联网搜索）
- `deep_think` 开关（深度思考）

### App.jsx — 主应用状态

- `sessions` / `activeSessionId` / `messages` 三级状态
- `handleSend()` 调 `chatApi.streamChat()`，注册 4 个回调：`onToken` / `onReasoning` / `onStructure` / `onEnd`
- 返回 abort 函数，切换会话时取消前一个请求
- Sidebar 新建会话时生成随机 `session_id`（UUID 截断）

### vite.config.js — SSE 代理

```js
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    configure: (proxy) => {
      proxy.on('proxyReq', (proxyReq) => {
        proxyReq.setHeader('X-Accel-Buffering', 'no')  // Nginx 禁用缓冲
      })
    }
  }
}
```

---

## 📝 日志与运维

### Loguru 日志系统（`logger.py`）

双输出：控制台彩色 + 文件按天轮转。

| 输出 | 格式 | 轮转 | 保留 |
|------|------|------|------|
| 控制台 stderr | `<green>time</green> \| <level>LEVEL</level> \| <cyan>name:function:line</cyan> - message` | — | — |
| 文件 `app_YYYY-MM-DD.log` | `time \| LEVEL \| name:function:line - message` | 每天零点 | 30 天 |

关键配置：`enqueue=True` 异步写入，避免多进程阻塞；`encoding="utf-8"` 支持中文日志。

### MySQL 连接池（`mysql_client.py`）

```python
engine = create_engine(
    settings.mysql_url,
    pool_pre_ping=True,   # 连接前 ping，避免使用 MySQL 已关闭的连接
    pool_recycle=3600,    # 1 小时主动回收，与 MySQL wait_timeout 对齐
    pool_size=10,         # 常驻 10 个连接
    max_overflow=20,      # 高峰最多 30 个
)
```

FastAPI 依赖注入 `get_db()`：请求 yield SessionLocal，finally 自动 close，确保连接不泄漏。

---

## 📊 数据规模

| 数据 | 数量 | 说明 |
|------|------|------|
| 景点种子 | **1,554** | 含坐标、等级、开放时间、票价 |
| 美食种子 | **80+** | 含推荐菜品、人均消费 |
| 避坑规则 | **250+** | 景点/交通/通用三类 |
| 硬规则 | **53** | 行程强制约束 |
| 通勤矩阵 | **190,158** | 景点对通勤时间/距离 |
| RAG Query Variants | **12,600+** | 覆盖描述/贴士/文化上下文 |

---

## 📁 项目结构

```
chengdu-travel-agent/
├── backend/
│   ├── app/
│   │   ├── agents/          # 🧠 多智能体
│   │   │   ├── graph.py       # LangGraph StateGraph 构建
│   │   │   ├── nodes.py       # Supervisor + 4 Worker 节点
│   │   │   ├── llm_client.py  # LLM 工厂（多模型切换）
│   │   │   └── utils.py       # validate_plan / haversine / 清洗
│   │   ├── rag/             # 📚 检索增强
│   │   │   ├── embeddings.py    # 嵌入模型 + Reranker
│   │   │   ├── llama_index_engine.py  # QueryEngine 构建
│   │   │   └── prompt_templates.py   # 双轨制 Prompt + 7 维度组
│   │   ├── api/             # ⚡ FastAPI 路由
│   │   │   ├── chat_routes.py    # /api/chat（SSE 流式）
│   │   │   ├── spot_routes.py    # /api/spots
│   │   │   └── health_routes.py  # /api/health
│   │   ├── tools/           # 🔧 外部工具
│   │   │   ├── amap_weather.py   # 高德天气
│   │   │   └── web_search.py     # 联网搜索
│   │   ├── database/        # 💾 数据层
│   │   ├── schemas/         # 📋 Pydantic 模型
│   │   ├── config.py        # ⚙️ Pydantic Settings 单例
│   │   ├── logger.py        # 📝 Loguru 日志
│   │   └── main.py          # 🚀 FastAPI lifespan + 启动
│   ├── scripts/             # 🛠️ 运维脚本
│   │   ├── 01_init_db_create_tables.py   # MySQL 建表
│   │   ├── 02_import_seeds.py            # CSV → MySQL
│   │   └── 03_build_rag_index.py         # Milvus 向量化
│   ├── data/                # 📂 数据（不在 Git 仓库中）
│   │   ├── seeds/             # 原始 CSV 种子
│   │   ├── augmented/         # RAG 增强 CSV
│   │   ├── milvus/            # Milvus Lite 本地 DB
│   │   └── models/            # BGE 模型权重
│   ├── tests/               # 🧪 pytest 测试
│   ├── launch_backend.py    # 🚀 启动入口（dotenv + LangSmith 注入）
│   └── requirements.txt
├── frontend/                # 🖥️ React + Vite
│   └── src/
│       ├── components/        # 8 个 UI 组件
│       │   ├── ChatInput.jsx
│       │   ├── MessageBubble.jsx
│       │   ├── CitationTag.jsx
│       │   ├── PlanCard.jsx
│       │   ├── QACard.jsx
│       │   ├── AdvicePanel.jsx
│       │   ├── NearbyList.jsx
│       │   └── Sidebar.jsx
│       └── api/chatApi.js     # SSE 客户端
└── README.md
```

---

## 🚀 快速启动

### 1. 后端
```bash
cd backend
pip install -r requirements.txt

# 配置环境变量（复制模板）
cp .env.example .env
# 编辑 .env 填入 DeepSeek API Key / MySQL / 高德地图 Key / LangSmith Token

# 初始化数据
python scripts/01_init_db_create_tables.py   # MySQL 建表
python scripts/02_import_seeds.py            # 导入 1554 景点 + 通勤矩阵
python scripts/03_build_rag_index.py         # 向量化 → Milvus Lite

# 启动
python launch_backend.py  # http://localhost:8000
```

### 2. 前端
```bash
cd frontend
npm install
npm run dev  # http://localhost:5173
```

---

## ⚠️ 已知局限 & 后续计划

> 坦诚地说，**这个项目还远不是生产级**。以下是我清楚的短板，也是我接下来想改进的方向。

### 🚧 当前局限

| 维度 | 现状 | 问题 |
|------|------|------|
| **并发** | 单进程 Uvicorn + SqliteSaver | SQLite WAL 在高并发下仍有锁争用，应切 RedisSaver 或 PostgresSaver |
| **鉴权** | JWT 已实现但前端未对接 | `/api/chat` 路由未强制 token，任何人可调用 |
| **数据新鲜度** | 种子 CSV 一次性导入 | 高德数据、票价、开放时间会变，缺少定时增量更新 |
| **前端** | Semi UI + Vite | 组件未抽离 Hook、无状态管理库（Zustand/Redux），对话历史用 localStorage |
| **测试覆盖** | 3 个 pytest 文件 | 只有 Agent / RAG / Worker 基本路径，缺少 API 集成测试 + 前端 E2E |
| **部署** | 本地运行 | 无 Dockerfile、无 CI/CD、无 HTTPS 证书 |
| **LTM** | 已实现向量去重 | 用户画像维度单一，未做多模态偏好（文本+交互行为） |

### 🗺️ 后续计划

- [ ] **鉴权打通**：前端 JWT 登录 + Token 刷新 + 路由守卫
- [ ] **多进程部署**：Gunicorn/Uvicorn Workers + RedisSaver 替换 SqliteSaver
- [ ] **数据管道自动化**：Airflow 或定时脚本，每日拉取高德最新数据 → MySQL → 重建 RAG 索引
- [ ] **前端重构**：Zustand 状态管理 + React 19 Server Components + PWA
- [ ] **可观测性升级**：LangSmith 全链路 + Prometheus/Grafana 指标 + Sentry 错误追踪
- [ ] **Docker + CI/CD**：GitHub Actions → Docker Image → 云服务器
- [ ] **多城市扩展**：从成都 → 西安 / 重庆 / 北京，验证架构可复用性
- [ ] **Eval 体系**：自建问题集 + 自动打分 + RAGAS / TruLens 评估

---

## 📄 License

MIT © FoeikNov
