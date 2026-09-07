# 🏯 蓉游智体 · Chengdu Travel AI Agent

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python)
![Node](https://img.shields.io/badge/Node.js-19+-green?logo=node.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2-1C3F94?logo=langchain)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)
![Milvus](https://img.shields.io/badge/Milvus-Lite-00A0FF?logo=milvus)
![MySQL](https://img.shields.io/badge/MySQL-8-4479A1?logo=mysql)
![License](https://img.shields.io/badge/License-MIT-yellow)

> 蓉游智体是一个面向真实用户场景的成都旅游 AI Agent：LangGraph 驱动 Supervisor 并行调度 4 个 Worker，LlamaIndex + Milvus 提供双轨制检索增强（硬事实锁死 + 软知识按需展开），8 条程序级硬规则 + 53 条 Prompt 硬规则保障行程合理性，SSE 流式输出实时渲染 Markdown 卡片。

---

## 🧭 项目定位

**一个可以跑起来的 Agent 工程化样本**——不是 Demo Toy，也不是纯论文复现。从种子数据采集、RAG 向量化、多智能体编排、SSE 流式输出到前端 Markdown 渲染，形成完整闭环。核心特色是：**把 LLM 的强项（语言理解、知识扩展、规划推理）和工程的确定性（数据校验、规则硬编码、程序级兜底）结合起来**。

### 🎯 解决什么问题

传统旅游问答只有两种体验：要么 LLM 编造票价（"武侯祠门票 60 元" → 实际 50 元），要么只给冷冰冰的景点列表。蓉游智体要做的是：

- **硬事实锁死**：票价、开放时间、通勤时间、评分等精确数字，**必须来自 RAG 检索内容**，检索中没有就说"暂无相关信息"
- **软知识按需展开**：历史文化、游玩攻略、拍照机位等 LLM 强项，按问题关键词动态激活 7 个维度组，结合预训练知识丰富回答
- **行程不踩坑**：8 条 Python 硬编码规则 + 53 条 Prompt 规则 + validate_plan 程序级校验，三重保障生成的行程符合真实地理约束
- **多意图并行**：用户问"熊猫基地怎么去 + 附近有什么吃的"，Supervisor 同时派发 QA + Nearby + Advice 三个 Worker，并行执行后汇总

### 🤖 Agent 架构特色

#### Supervisor-Worker 模式：不是单 Agent 硬扛，是分工协作

传统 RAG Agent 是"一个 LLM + 一个检索器"，所有问题走同一条链路。蓉游智体用 LangGraph 的 StateGraph 把问题拆成 4 种专长 Worker：

```
用户问题 → Supervisor（意图分类）
              │
              ├─ qa_worker     → LlamaIndex + Milvus 双轨制 RAG
              ├─ plan_worker   → SQL 查硬规则/通勤矩阵 + LLM 生成 + validate_plan 程序校验
              ├─ advice_worker → MySQL 查避坑规则 + LLM 六维组织
              └─ nearby_worker → LLM 识别景点名 + MySQL 查坐标 + Haversine 球面距离
```

关键设计决策：
- **Send API 并行**：4 个 Worker 同时启动，共享 State，结果通过自定义 reducer 自动合并，总耗时 ≈ 最慢那个 Worker
- **两轮职责复用同一节点**：Supervisor 通过 `state["phase"]` 和 `worker_results` 是否为空自动切换 routing/summary，省一个节点
- **Intent fallback 链路**：JSON 解析失败 → 默认 qa_worker；RAG 检索为空 → 回退 LLM 软知识（强制数字序号列表）；Supervisor 汇总 LLM 失败 → 直接拼接 Worker 原始结果
- **Checkpointer 隔离**：每次请求生成唯一 `thread_id = session_id + timestamp + uuid8`，跨请求永不串状态，但同一请求内 Checkpointer 保证 State 不丢

#### 双轨制 Prompt：硬事实锁死，软知识放开

| 轨道 | 内容 | 来源 | LLM 自由度 |
|------|------|------|-----------|
| 🔒 硬事实 | 票价 / 开放时间 / 通勤 / 评分 / 地址 | RAG 检索内容 | 零——必须原样使用，没有就说"暂无相关信息" |
| 📖 软知识 | 历史 / 攻略 / 天气 / 人群 / 交通 / 周边 / 装备 | LLM 预训练知识 + 7 维关键词触发 | 高——按问题类型动态拼接维度组，允许自由扩展 |

实现方式：`DynamicTextQAPrompt` 继承 LlamaIndex `PromptTemplate`，重写 `format()` 方法，在运行时调 `build_qa_prompt(query, context)` 动态拼接 `QA_BASE_PROMPT` + `G1~G7` 中命中的维度组。不是固定模板 → 是运行时根据 query 关键词决定哪些维度组激活。

#### 三层防幻觉：Prompt + 代码 + 校验

| 层级 | 机制 | 特点 |
|------|------|------|
| **数据层** | 12,605 条 Query Variants 覆盖三大长文本 | 扩大召回面，减少"检索不到"导致的幻觉 |
| **检索层** | 向量 + BM25 → 融合 → Reranker → KeywordBoost 后处理 | 5 级流水线，`source_name` 重叠加权 + `travel_tips` 硬事实块额外 ×1.3 |
| **Prompt 层** | `QA_BASE_PROMPT` 硬事实规则 + `SOFT_KNOWLEDGE_GROUPS` 软知识分组 | 明确告知 LLM 哪些可以编、哪些不能编 |
| **代码层** | `validate_plan()` 8 条 Python 硬编码规则 | R-001 强制覆盖熊猫基地（最后执行，保留原安排）；R-002~R-008 检测型只记录 |
| **降级层** | 8 项 fallback（意图分类 / MySQL / RAG / 汇总 / 识图 / 天气 / 联网 / JSON） | 任何环节出问题都不返回 500，要么降级要么返回兜底内容 |

#### 其他 Agent 工程细节

| 细节 | 实现 |
|------|------|
| **多模型切换** | 6 个预创建 ChatOpenAI 实例（fast / pro / reasoner / vision / json / worker），`get_llm(mode, deep_think)` 工厂选择；`llm_json` 和 `llm_worker` 必须 non-streaming，否则 JSON 输出/卡片内容会泄漏到聊天流式响应 |
| **SSE 流式** | `astream_events` 只用一次 + `event_type` 分发；4 种事件（token / reasoning / structure_ready / end）；Worker 卡片先行推送，最终汇总后推 end |
| **DeepSeek 兼容** | Monkey-Patch 三部曲：模型注册表注入 4 种 DeepSeek 模型 → tiktoken 映射到 cl100k_base → API 端点覆盖为 `chat.completions.create()` |
| **Checkpointer 工厂** | `CHECKPOINT_BACKEND` 环境变量一行切换 sqlite / postgres / redis / memory；默认 SqliteSaver（WAL + 30s timeout） |

### 📊 数据规模

| 维度 | 数量 | 来源 |
|------|------|------|
| 成都景点 | **1,554** | 覆盖全部 22 个区县，含坐标/等级/票价/开放时间/描述/贴士/文化上下文 |
| 美食种类 | **80** | 火锅/串串/川菜/小吃/凉菜/甜品等 8 大类 |
| 美食店铺 | **1,624** | 含评分/人均/商圈 |
| 避坑规则 | **250** | 景点/交通/天气/购物/排队等 10 大场景 |
| 硬规则 | **53** | 含 R-001~R-008 程序级强制规则 |
| 通勤矩阵 | **190,157** | 高德地图 API 批量计算，覆盖 100% 景点对的双向通勤 |
| RAG Query Variants | **12,605** | 覆盖 description / travel_tips / cultural_context 三大长文本的多种用户问法 |

### 🔑 与传统 RAG 的差异化

| 维度 | 传统 RAG | 蓉游智体 |
|------|---------|---------|
| **Agent 架构** | 单 LLM + 单检索器 | LangGraph Supervisor + 4 专长 Worker，Send API 并行派发 |
| 检索链路 | 向量 Top-K | 向量 Top10 + BM25 Top10 → 融合 → Reranker Top3 → KeywordBoost 后处理 |
| Prompt | 固定模板 | 双轨制（硬事实锁死 + 7 维软知识按需拼接） |
| 行程生成 | 单次 LLM 调用 | SQL 查硬规则 + 通勤矩阵 → LLM 生成 → validate_plan 程序级校验 |
| 多意图 | 串行处理 | LangGraph Send API 并行派发多个 Worker |
| 输出 | 纯文本 | SSE Token 流式 + Worker 结构化卡片先行 + 最终 Markdown 汇总 |
| 幻觉防护 | "not prior knowledge" 提示 | 硬事实强制来自检索 + 8 条 Python 规则 + 53 条 Prompt 规则 |
| **工程兜底** | 无 fallback | 8 项降级策略，任何环节出问题都不返回 500 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│  👤 用户                                                         │
│  SSE 流式 / HTTP POST                                            │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  🖥️ 前端 · React 19 + Vite 8 + Semi UI                          │
│  Chat 页面 → /api/chat → sse.js(EventSourcePolyfill) → 4 回调     │
│  3 种模式: 文字问答 / 行程规划 / 图片识图                          │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼ POST /chat (SSE)
┌─────────────────────────────────────────────────────────────────┐
│  ⚡ FastAPI 0.115 + Uvicorn 0.30                                  │
│  chat_routes / spot_routes / health_routes                       │
│  lifespan 启动 Milvus + MySQL；关闭时释放连接                     │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼ LangGraph astream_events
┌─────────────────────────────────────────────────────────────────┐
│  🧠 多智能体层 · LangGraph StateGraph                              │
│                                                                   │
│  ┌─────────────── Supervisor ───────────────┐                    │
│  │ 意图分类 → Send API 并行派发 → 汇总输出   │                    │
│  │ 两轮复用同节点: phase=routing / summary  │                    │
│  └───────┬────────┬────────┬────────┬──────┘                    │
│          │Send     │Send     │Send     │Send                      │
│          ▼         ▼         ▼         ▼                          │
│  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐              │
│  │QA Worker ││Plan      ││Advice    ││Nearby    │              │
│  │双轨制RAG ││硬规则+   ││六维避坑 ││Haversine │              │
│  │          ││validate  ││          ││球面距离  │              │
│  └────┬─────┘└────┬─────┘└────┬─────┘└────┬─────┘              │
│       │           │           │           │                       │
│       └───────────┴───────────┴───────────┘                       │
│                           ▼ reducer 自动合并 worker_results        │
└──────────────────────────┬──────────────────────────────────────┘
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────┐
│ 📚 RAG 检索增强  │ │ 🗄️ MySQL 8.0    │ │ 🔧 工具层               │
│ LlamaIndex +    │ │ 9 张表:         │ │ · 高德天气 (httpx)      │
│ Milvus Lite     │ │ spots/foods/    │ │ · DuckDuckGo 联网搜索   │
│                 │ │ avoid_rules/    │ │ · DeepSeek Chat API     │
│ 向量→BM25→融合  │ │ hard_rules/     │ │   Monkey-Patch 三步适配 │
│ →Rerank→Boost   │ │ transit_matrix  │ │                         │
│                 │ │ SQLAlchemy 连接池│ │                         │
│ BGE-large 1024d │ │ pool_size=10    │ │                         │
│ + bge-reranker  │ │ pool_recycle=1h │ │                         │
└─────────────────┘ └─────────────────┘ └─────────────────────────┘
```

**请求完整链路**：

```
POST /chat → Supervisor 意图分类
  ├─ 问候/天气 → 旁路直接返回（不派发 Worker）
  ├─ 识图     → vision 模型直接分析（跳过 Worker）
  └─ 正常     → Send API 并行派发 N 个 Worker
       ├─ QA → QueryEngine(向量+BM25融合) → Reranker → KeywordBoost → 双轨制 Prompt → LLM
       ├─ Plan → MySQL 查硬规则+通勤矩阵 → LLM 生成 → validate_plan 8 条校验
       ├─ Advice → MySQL 查避坑规则 → LLM 六维组织
       └─ Nearby → MySQL 查坐标 → Haversine 球面距离排序
  → Supervisor 汇总 → _clean_markdown → SSE 推 end
```

---

## 🧰 技术栈

### ⚡ 后端框架 & 中间件

| 技术 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.115 | ASGI Web 框架，类型安全路由 + lifespan 生命周期 |
| Uvicorn | 0.30 | 异步 ASGI 服务器，`[standard]` 依赖 httptools + uvloop |
| Pydantic | 2.9 | 数据校验 + `BaseSettings` 配置单例 |
| Pydantic Settings | 2.5 | `.env` 文件注入 + 环境变量覆盖 |
| python-multipart | 0.0.9 | Vision 模式图片上传支持 |
| httpx | 0.27 | 高德天气 API + 异步 HTTP 客户端 |
| aiofiles | 24.1 | 异步文件操作预留 |

### 🤖 AI Agent 核心（LangGraph + LangChain 生态）

| 技术 | 版本 | 用途 |
|------|------|------|
| **LangGraph** | 0.2 | StateGraph + Send API 并行调度，`astream_events` 流式输出 |
| LangChain | 0.3 | 统一 LLM 抽象 / Runnable / 消息协议 |
| LangChain Core | 0.3 | `BaseMessage` / `SystemMessage` / `HumanMessage` 等核心类型 |
| LangChain Community | 0.3 | 社区扩展 |
| LangSmith | ≥0.1.120 | 全链路 Trace 可观测性 |
| tenacity | 8.5 | LLM 调用自动重试 |
| tiktoken | 0.8 | Token 近似计数（`MODEL_TO_ENCODING` 映射 DeepSeek → cl100k_base） |
| **DeepSeek API** | — | Chat API 完全兼容 OpenAI，4 种模型切换：chat / v4-pro / reasoner / v4-flash-vision |

### 📚 RAG 检索增强（LlamaIndex + Milvus + BGE）

| 技术 | 版本 | 用途 |
|------|------|------|
| LlamaIndex | — | QueryEngine / Retriever / ResponseSynthesizer |
| Milvus Lite | ≥3.0 | 本地文件向量存储（`.db` 文件，零服务端依赖） |
| PyMilvus | ≥2.5 | Milvus Python SDK，`MilvusVectorStore` 对接 |
| Sentence Transformers | 3.1 | `BAAI/bge-large-zh-v1.5`（1024 维中文嵌入）+ `bge-reranker-large`（重排） |
| rank_bm25 | 0.2 | BM25 稀疏检索，单字 `token_pattern` 适配中文 |
| jieba | 0.4 | 中文分词（BM25 辅助） |

### 💾 数据层

| 技术 | 版本 | 用途 |
|------|------|------|
| MySQL | 8.0 | 9 张表持久化：spots / foods / food_shops / avoid_rules / hard_rules / transit_matrix / chat_sessions / user_profiles / dlq |
| SQLAlchemy | 2.0 | ORM + `create_engine(pool_pre_ping, pool_recycle=3600, pool_size=10, max_overflow=20)` |
| PyMySQL | 1.1 | MySQL 异步驱动 |
| Redis | 5 | Checkpointer 备选后端（当前未启用，默认 SqliteSaver） |
| **SqliteSaver** | ≥2.0（langgraph-checkpoint-sqlite） | LangGraph 跨重启 Checkpointer，WAL 模式 + 30s timeout |

### 🖥️ 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 19 | UI 框架 |
| Vite | 8 | 构建工具 + SSE 代理（`X-Accel-Buffering: no`） |
| Semi UI | 2.103 | 组件库（Card / Tag / Typography / Space） |
| SSE.js | 2.8 | EventSourcePolyfill 实现 POST + SSE |

### 🔧 工具 & 运维

| 技术 | 版本 | 用途 |
|------|------|------|
| python-dotenv | 1.0 | `.env` 加载（Launcher 启动时注入） |
| Loguru | 0.7 | 结构化日志，控制台彩色 + 文件按天轮转 + 30 天保留 + `enqueue=True` 异步写入 |
| pandas | 2.2 | CSV 种子数据加载 |
| numpy | 1.26 | Haversine 球面距离计算 |
| requests | 2.32 | DuckDuckGo HTML 联网搜索（非异步，降级用） |
| tqdm | 4.66 | 向量化进度条 |
| pytest | 8.3 | 测试框架 |
| pytest-asyncio | 0.24 | 异步测试支持 |

### 🛠️ 外部 API

| 服务 | 用途 | 降级策略 |
|------|------|---------|
| **高德开放平台**（`restapi.amap.com/v3/weather/weatherInfo`） | 成都天气查询 + 通勤矩阵计算数据源 | `AMAP_API_KEY` 未配置 → 返回"暂不可用" |
| **DuckDuckGo HTML**（`html.duckduckgo.com/html/`） | 联网搜索增强时效性 | 国内不稳定 → 返回空字符串 → 纯 RAG 回答 |
| **LangSmith**（`api.smith.langchain.com`） | 全链路 Trace 可观测性 | `LANGCHAIN_TRACING_V2=false` 时关闭 |

---

## ⚙️ 配置中心（Pydantic Settings）

`config.py` 用 `BaseSettings` 实现类型安全的单例配置。**为什么用 Pydantic Settings 而不是 yaml/json/toml**：三个理由——类型安全（`MYSQL_PORT: int` 不是字符串 3306）、环境变量自动覆盖（`.env` 不存在时从系统环境变量读，CI/CD 直接注入）、全项目单例（`from app.config import settings` 一行搞定，不传 config 参数）。

```python
# SettingsConfigDict — 三个关键设计决策
model_config = SettingsConfigDict(
    env_file=".../.env",          # .env 文件路径
    extra="ignore",               # .env 里多写了字段不报错（向后兼容）
    case_sensitive=True,          # 区分大小写，避免 MYSQL_HOST vs mysql_host 混淆
)
```

**Milvus Lite 自动切换**：`MILVUS_DB_PATH` 字段一个值决定两种模式——填 `"127.0.0.1:19530"` → Standalone 远程连接；填 `"data/milvus.db"` → Milvus Lite 本地文件存储。`is_milvus_lite` @property 检测 `.db` 后缀，`milvus_uri` @property 自动转换为正确的 URI 格式。本地开发用 Lite（零依赖），生产部署改环境变量切 Standalone。

**派生属性（@property）**——为什么不直接存字符串：

| 属性 | 计算逻辑 | 为什么不直接存 |
|------|---------|---------------|
| `mysql_url` | `mysql+pymysql://user:pass@host:port/db?charset=utf8mb4` | 密码变了不用改 URL，只改 `MYSQL_PASSWORD` |
| `redis_url` | 有密码时 `redis://:pass@host`，无密码时 `redis://host` | 自动处理密码前缀（Redis URL 密码前要加 `:`） |
| `is_milvus_lite` | `MILVUS_DB_PATH.endswith(".db")` | 一个字段切两种模式，不用单独的 `MILVUS_MODE` |
| `milvus_uri` | Lite 返回文件路径，Standalone 返回 `http://host:port` | 适配 MilvusVectorStore 两种连接方式 |
| `langsmith_enabled` | `LANGCHAIN_TRACING_V2.lower() in ("true", "1", "yes")` | 兼容 `.env` 字符串和系统环境变量 |

**完整配置表**（按代码顺序）：

| 分组 | 配置 | 默认值 | 说明 |
|------|------|--------|------|
| **LLM** | `DEEPSEEK_MODEL` | `deepseek-chat` | 快速模式 |
| | `DEEPSEEK_MODEL_PRO` | `deepseek-v4-pro` | 专家模式 |
| | `DEEPSEEK_MODEL_REASONER` | `deepseek-reasoner` | 深度思考（带 `<think>`） |
| | `DEEPSEEK_MODEL_VISION` | `deepseek-v4-flash-vision-exp` | 识图模式 |
| | `DEEPSEEK_TEMPERATURE` | `0.3` | 默认温度，各 Worker 可覆盖 |
| **高德** | `AMAP_API_KEY` | `""` | 天气 + 通勤矩阵计算 |
| **MySQL** | `MYSQL_DB` | `chengdu_travel` | 9 张表 |
| **Milvus** | `MILVUS_DB_PATH` | `127.0.0.1:19530` | `.db` 后缀自动切 Lite |
| | `MILVUS_COLLECTION_SPOTS` | `chengdu_spots` | RAG 集合 |
| | `MILVUS_COLLECTION_LTM` | `user_ltm_v1` | LTM 用户画像集合（schema-only） |
| | `MILVUS_DIM` | `1024` | BGE 向量维度 |
| **LTM** | `LTM_DEDUP_THRESHOLD` | `0.92` | 语义去重阈值 |
| **Embedding** | `EMBED_MODEL_NAME` | `BAAI/bge-large-zh-v1.5` | 中文嵌入 |
| | `RERANKER_MODEL_NAME` | `BAAI/bge-reranker-large` | 重排器 |
| **Checkpoint** | `CHECKPOINT_BACKEND` | `sqlite` | 可选 memory/redis/postgres |
| **LangSmith** | `LANGCHAIN_TRACING_V2` | `"true"` | 全链路追踪开关 |

---

## ✨ 核心特性

> 下面每一条都不是"用了 LangGraph/RAG"这种套话，而是**在 LangGraph/RAG 基础上做了什么不一样的事**。

### 🎯 1. Supervisor 两轮复用 + Send API 并行——比多 Agent 框架更轻

**别人的多 Agent**：每个 Worker 是独立节点 + 单独路由，N 个 Worker 需要 2N 个节点。

**蓉游智体**：Supervisor 通过 `state["phase"]` 字段**两轮复用同一个节点**——首轮 `phase=routing` 做意图分类，次轮 `phase=summary` 做结果汇总。Worker 执行期间 Supervisor 处于"等待 Send 回调"状态，不消耗 LLM Token。

```python
# nodes.py — 同一个 supervisor 函数，两轮职责靠 phase 区分
if state["phase"] == "routing":
    workers = classify_intent(state["messages"])
    return Send([build_worker_call(w, state) for w in workers])
else:  # phase == "summary"
    return summarize(state["worker_results"])
```

关键设计：
- `Send([...])` 而不是 `Command(goto=worker)`——LangGraph 原生命令，Worker 并行执行、各自独立重试、结果通过自定义 reducer 自动合并回 `worker_results`
- Intent 分类走 LLM 但有三重兜底：JSON 解析失败 → 默认 `["qa_worker"]`；Worker 名不在 `VALID_WORKERS` 集合 → 过滤；过滤后为空 → 默认 `["qa_worker"]`
- 3 条旁路不派发 Worker：短消息（≤10 字符）命中 30 个问候关键词 → 固定回答；23 个天气关键词 → `get_weather()`；识图模式 → vision 模型直接分析

### 🔍 2. RAG 双轨制——硬事实锁死 vs 软知识放开，不是一刀切的"not prior knowledge"

**别人的 RAG**：检索到什么就喂 LLM，检索不到就让 LLM 说"我不知道"。

**蓉游智体**：把问题拆成两个轨道，给 LLM 明确的权限边界。

| 轨道 | 规则 | Prompt 中的措辞 |
|------|------|----------------|
| 🔒 硬事实 | 必须来自检索内容，没有就说"暂无" | `检索中未找到票价信息，请勿编造` |
| 📖 软知识 | 按关键词动态激活 G1~G7 维度组，LLM 自由扩展 | `你可以结合历史背景发挥，但标注为推测` |

实现核心是 `DynamicTextQAPrompt`——继承 LlamaIndex `PromptTemplate`，**重写 `format()` 方法**，在运行时调 `build_qa_prompt(query, context)` 根据 `detect_groups()` 匹配到的关键词动态拼接 `QA_BASE_PROMPT` + 命中的维度组。不是模板里写死 7 组，而是运行时决定拼哪几组。

检索链路 5 级流水线（比标准 RAG 多 2 级）：

```
向量 Top10 + BM25 Top10 → QueryFusionRetriever 融合 Top20 → bge-reranker Top3 → KeywordBoost 后处理 → 双轨制 Prompt → LLM
                                                                                         ↑
                                                                          source_name 重叠加权 + travel_tips ×1.3
```

### 🛡️ 3. validate_plan 8 条 Python 硬编码——Prompt 管不住的用代码管

**别人的行程生成**：靠 Prompt 里写"请合理安排"，但 LLM 还是可能把都江堰和青城山拆到两天、或者给 ≤3 天行程塞 Leshan 大佛。

**蓉游智体**：`validate_plan()` 是纯 Python 函数，在 Plan Worker 输出后**程序级校验 + 自动修正**，不依赖 LLM 自觉。

| 规则 | 类型 | 执行时机 | 修正方式 |
|------|------|---------|---------|
| R-001 熊猫基地 Day1 08:00-12:00 | 强制覆盖 | 最后执行 | 把原安排移到下午，熊猫基地插上午 |
| R-002 都江堰+青城山不同市区混排 | 检测型 | 先执行 | 记录到 `plan["rules_applied"]` |
| R-003 武侯祠+锦里同半天 | 检测型 | 先执行 | 同上 |
| R-004 杜甫草堂+金沙同半天 | 检测型 | 先执行 | 同上 |
| R-005 周一排除金沙/川博 | 检测型 | 先执行 | 同上 |
| R-006 每日 ≤3 景点 | 检测型 | 先执行 | 同上 |
| R-007 每日通勤 ≤180 分钟 | 检测型 | 先执行 | 同上 |
| R-008 亲子/老人排除西岭雪山 | 检测型 | 先执行 | 同上 |

为什么 R-001 最后执行？因为它是**强制覆盖型**，会主动修改 plan 结构；其他 7 条是**检测型**，只记录不修改。先跑完检测，再强制覆盖，最后输出的 plan 同时满足两类规则。

### 🚇 4. 19 万条通勤矩阵——让 LLM 的行程时间有据可查

**别人的行程规划**：LLM 自己编通勤时间（"熊猫基地到春熙路约 40 分钟" → 实际可能 1 小时）。

**蓉游智体**：Plan Worker 生成行程前，SQL 查 `transit_matrix` 表（`LIMIT 20`，按 same_region 优先），结果作为 `{transit_matrix}` 占位注入 `PLAN_PROMPT`。LLM 看到的是**真实的通勤时间/距离对**，而不是让它自己编。

数据来源：高德地图 `distance` 批量 API（100 点/请求），两阶段计算：
1. 区域内（same_region=1）全精确计算
2. 跨区域 Top100 热门景点精确计算，覆盖 100% 景点对

Nearby Worker 还用 Haversine 球面距离（地球半径 6371km）做周边推荐——MySQL 存的是经纬度，Haversine 算直线距离，半径策略：市区 3km / 默认 5km / 郊区 10km。

### 🧩 5. 六模型工厂 + DeepSeek Monkey-Patch——让 LangChain 兼容国产 LLM

**问题**：DeepSeek Chat API 虽然兼容 OpenAI，但 LangChain 的 `ChatOpenAI` 内部有三处硬编码假设：模型注册表、tiktoken 映射、API 端点路径，直接用会报 `Model xxx not found`。

**解法**：`llm_client.py` 里三步 Monkey-Patch：

```python
# 1. 模型注册表注入 4 种 DeepSeek 模型
ModelRegistry.register_model("deepseek-chat", ...)
ModelRegistry.register_model("deepseek-v4-pro", ...)
ModelRegistry.register_model("deepseek-reasoner", ...)
ModelRegistry.register_model("deepseek-v4-flash-vision", ...)

# 2. tiktoken 映射到 cl100k_base（DeepSeek 用的 tokenizer）
MODEL_TO_ENCODING = {"deepseek-chat": "cl100k_base", ...}

# 3. API 端点覆盖为 chat.completions.create()
original_create = ChatCompletion.create
def patched_create(*args, **kwargs): ...
```

同时预创建 6 个实例（fast / pro / reasoner / vision / json / worker），`get_llm(mode, deep_think)` 工厂选择。`llm_json` 和 `llm_worker` **必须 non-streaming**——否则 JSON 输出/卡片内容会泄漏到聊天的流式响应里。

### 💨 6. SSE 流式 + 4 种事件类型——Worker 卡片先行，最终汇总后推 end

**别人的 SSE**：只有 `token` 一种事件，用户看到的是纯文本逐字输出。

**蓉游智体**：4 种事件 + Worker 卡片先行：

```
event: token           → LLM 流式 token，实时渲染
event: reasoning       → 深度思考内容（<think> 标签或 reasoning_content 字段）
event: structure_ready → Worker 完成，推结构化卡片（QA 问答卡 / Plan 行程卡 / Advice 建议卡）
event: end             → Supervisor 汇总完成，推最终 Markdown
```

实现关键：`astream_events` **只用一次**——LangGraph 的 astream 如果分两次调，第二次会从 Checkpointer 恢复后跳过已执行的 Worker。所以整个图只调一次，事件通过 `event_type` 分发。`worker_results` 完成后立即推 `structure_ready`，用户在 LLM 还在汇总时就已经能看到各个 Worker 的输出卡片。

---

## 🔌 API 接口协议

### FastAPI lifespan 启动流程

`main.py` 用 `@asynccontextmanager` 做启动预热和关闭清理。**为什么要预热**：BGE 嵌入模型首次加载需要 30 秒，如果在第一个用户请求时才加载，第一个用户会等 30 秒白屏。预热把这个成本转移到启动阶段。

```
启动顺序（三个 try 块，任何一个失败都不阻断启动）：
1. MySQL SELECT 1 → 验证连接池可用
2. import llm → 验证 DeepSeek API Key 已配置
3. _ensure_settings() → 把 BGE Embedding 绑定到 LlamaIndex Settings（关键！）
   否则第一个 Worker 调 RAG 时，Settings._embed_model 还是 None
   → LlamaIndex 尝试自动解析为 OpenAI Embedding → 炸掉
```

**CORS 设计决策**：`allow_origins=["*"]` + `allow_credentials=False`。为什么不用精确白名单——Vite proxy 模式下浏览器不会发 CORS（前端和后端同源），但穿透工具（如 Postman 直连）会发。`["*"]` 放开，`credentials=False` 配合（`*` 和 `credentials=True` 在 FastAPI 中不能同时用，浏览器会拒绝携带 Cookie）。

### `GET /health` — 全链路健康检查

逐项探测 MySQL / Milvus / LLM API Key / Checkpointer / Redis，前端可据此做连接状态指示灯。**Milvus 探测方式**：Lite 模式检查 `.db` 文件是否存在；Standalone 模式查 `list_collections()`。**LLM 探测**：只检查 `DEEPSEEK_API_KEY` 是否非空，不实际调 API（省 Token）。

```bash
curl http://localhost:8000/health
```

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

```bash
curl "http://localhost:8000/api/spots?keyword=熊猫&spot_level=4A&limit=5"
```

### `GET /api/spots/{spot_id}` — 景点详情

返回完整字段，含 `description` / `travel_tips` / `cultural_context` 三个长文本（RAG 向量化源）和 `avg_visit_hours`。

### `POST /api/chat` — SSE 流式对话

**唯一的 Agent 入口**。请求体：

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "message": "我想规划 3 天行程",
    "session_id": "user_abc123",
    "mode": "expert",
    "deep_think": false,
    "smart_search": false
  }'
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `message` | string | ✅ | 用户问题 |
| `session_id` | string | ✅ | 会话 ID（多会话隔离，Checkpointer 持久化用） |
| `mode` | enum | ❌ | `fast`(默认) / `expert` / `vision` |
| `deep_think` | bool | ❌ | 开启深度思考 → reasoner 模型（带 `<think>` 标签） |
| `smart_search` | bool | ❌ | 联网搜索（DuckDuckGo HTML，可能失败） |
| `image` | string | ❌ | 图片 base64 dataURL（vision 模式） |

**SSE 连接生命周期**：

```
POST /chat → FastAPI 验证请求体 → Lifespan 已预热
  → Supervisor 意图分类（可能走旁路）
    → Send API 派发 Worker（并行执行）
      → Worker 完成推 structure_ready
    → Supervisor 汇总（可能调 smart_search）
  → 推 end 事件 → 连接关闭
```

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

## 👷 四个 Worker 实现细节

每个 Worker 都是**独立的 LangGraph 节点**，通过 `Send([...])` 原生命令并行调用，结果通过 `worker_results` 自定义 reducer 自动合并。每个 Worker 内部有独立的 MySQL 降级逻辑（try/except 不阻断后续 Worker）。

### 📋 Worker 调用总览

```python
# LangGraph Send API — 并行派发，各自独立执行
return Send([
    Command(goto=qa_worker, update={...}),
    Command(goto=plan_worker, update={...}),
    Command(goto=advice_worker, update={...}),
    Command(goto=nearby_worker, update={...}),
])
```

Worker 选择逻辑由 Supervisor LLM 输出 JSON 决定，5 条判断规则（见 `SUPERVISOR_PROMPT`）：

| 用户输入 | 意图分类结果 |
|---------|-------------|
| "杜甫草堂门票多少钱" | `["qa_worker"]` |
| "帮我规划 3 天行程" | `["plan_worker"]` |
| "我想去杜甫草堂"（模糊） | `["qa_worker", "nearby_worker", "advice_worker"]` |
| "有什么避坑建议" | `["advice_worker"]` |
| "春熙路附近有什么" | `["nearby_worker"]` |

---

### 🔍 QA Worker — RAG 双轨制 + 软知识回退

**核心链路**：用户问题 → LlamaIndex `QueryEngine.aquery()` → 双轨制 Prompt → LLM 生成

**RAG 为空的判断逻辑**（四条件 OR）：
```python
is_empty = (
    not content
    or content.lower() in ("empty response", "none", "null")
    or "知识库中暂无" in content
)
```

**软知识回退 Prompt 关键约束**：
- 必须说明"以下内容来自通用知识而非景点数据库"
- 必须用**数字序号列表**（1. xxx 2. xxx）
- 禁止开场白/结尾语
- 禁止 `#` / `**` / `` ` `` / `|` / `---` 等符号

回退用 `llm_worker`（non-streaming），因为需要拿到完整输出再交给 Supervisor 汇总，不能让 token 泄漏到聊天流式响应。

---

### 📅 Plan Worker — SQL 动态注入 + validate_plan 程序级强制

**三阶段流水线**：SQL 查数据 → LLM 生成 JSON → `validate_plan()` 程序校验

**SQL 查询三条**（每条独立 try/except）：
```sql
-- 1. 硬规则（53 条，按 priority ASC 排序）
SELECT rule_content, reason, priority FROM hard_rules ORDER BY priority ASC

-- 2. 通勤约束（同区域优先，取 20 条）
SELECT from_spot_name, to_spot_name, transit_mode, duration_min
FROM transit_matrix WHERE same_region=1 LIMIT 20

-- 3. 行程模板（⚠️ MySQL 表未创建，try/except 降级为"无行程模板"）
SELECT template_json FROM itinerary_templates LIMIT 5
```

**PLAN_PROMPT 输出 JSON Schema**：
```json
{
  "title": "行程标题",
  "start_date": "YYYY-MM-DD",
  "days": [{
    "day": 1,
    "morning": {"spot_name": "...", "time": "08:00-12:00", "desc": "..."},
    "afternoon": {"spot_name": "...", "time": "13:00-17:00", "desc": "..."},
    "evening": {"spot_name": "...", "time": "18:00-21:00", "desc": "..."},
    "transit_minutes": 90,
    "budget": 300
  }],
  "total_budget": 3000,
  "group_type": "亲子/情侣/老人/学生/通用"
}
```

**关键设计**：`validate_plan(plan)` 返回的是**修改后的 dict**（不是异常），Plan Worker 直接把 dict 塞进 `worker_results`，前端 PlanCard 需要 `JSON.parse` 渲染，所以**不做 `json.dumps`**。

---

### 💡 Advice Worker — MySQL 避坑规则 + 六维强制输出

**SQL 查询**：只取高优先级避坑规则（severity='high'，LIMIT 15），避免 Prompt 过长。

**ADVICE_PROMPT 六维强制格式**：
```
1. 🌤 天气与季节
2. 💰 预算参考
3. 🚇 交通出行
4. ⚠️ 避坑提醒  ← 从 avoid_rules 表注入
5. 🍜 美食推荐
6. 📸 拍照攻略
```

格式约束：用 `##` 二级标题 + emoji 前缀，嵌套列表用 `- 顶层 + ○ 子项`，**禁止表格/加粗/代码块/分隔线**——因为前端 QACard 只支持基础 Markdown。

---

### 📍 Nearby Worker — Bounding Box 预过滤 + Haversine 精算

**两阶段地理计算**：Bounding Box 粗筛 → Haversine 精算

**为什么要 Bounding Box**：Haversine 公式对每个景点都要算一次 sin/cos，1554 个景点就是 1554 次三角函数。先用经纬度做 Bounding Box 粗筛（`1° ≈ 111km`，SQL 直接 BETWEEN），把候选集从 1554 降到几十，再用 Haversine 精算，速度提升 10-50x。

```sql
-- Bounding Box 预过滤（1°≈111km）
SELECT spot_name, longitude, latitude, rating FROM spots
WHERE longitude BETWEEN :lon_min AND :lon_max
  AND latitude BETWEEN :lat_min AND :lat_max
```

**Haversine 公式**（`utils.py`）：
```python
def haversine(lon1, lat1, lon2, lat2):
    R = 6371.0  # 地球半径 km
    ...
```

**排序 + 截断**：按 `distance_km` 升序排，取 TOP 10，返回 `[{"name": "...", "distance_km": 1.2, "rating": 4.8}, ...]`——直接传 list 不做 `json.dumps`，前端 NearbyList 直接解析。

**LLM 半径决策**（`NEARBY_PROMPT`）：
```json
{"spot_name": "宽窄巷子", "radius_km": 3}
```
半径策略：市区 3km / 默认 5km / 郊区（都江堰/青城山）10km。LLM 识别景点名后决定半径，不是硬编码。

---

## 🔧 工具层

### 高德天气——为什么选它不选 OpenWeatherMap

**选择理由**：高德 API 对成都做过本地化，返回的是中文天气描述（"多云"而非"cloudy"），且 `extensions="all"` 一次返回 3 天预报（含白天/夜间温度差），对旅游行程规划比 OpenWeatherMap 的 16 天预报更精准。价格方面，高德个人开发者每天 5000 次免费额度，完全够用。

```
GET https://restapi.amap.com/v3/weather/weatherInfo
    ?key=settings.AMAP_API_KEY
    &city=510100          ← 成都 ADCODE，硬编码在 amap_weather.py
    &extensions=all       ← base=实况单天 / all=预报3天
    &output=JSON
```

**返回解析**：高德 API 返回 JSON `status != "1"` 时表示失败（配额用尽 / Key 无效），不抛异常，而是返回 `"天气查询失败：{info}"`。`WEATHER_MAP` 兜底映射处理高德可能返回的英文/代码天气现象（sunny→晴）。

**调用链路**：用户问"成都明天下雨吗" → Supervisor 23 个 `WEATHER_KEYWORDS` 命中 → **不派发任何 Worker** → `get_weather("成都", "all")` 拿到 3 天预报 → LLM 润色成"明天白天多云转小雨，记得带伞" → 直接返回。**这个旁路跳过了 Send API 派发、RAG 检索和 Supervisor 汇总，一条 150ms 的 HTTP 请求 + 一次 LLM 调用完成。**

### DuckDuckGo HTML 搜索——为什么不用 SerpAPI/Bing API

**选择理由**：DuckDuckGo HTML 版**完全免费**（不需要 API Key），虽然国内不稳定（约 30% 概率超时/被拦截），但降级成本为零——返回空字符串，Supervisor 不追加搜索结果，Agent 自动退化为纯本地 RAG 回答。作为"增强时效性"的可选开关（`smart_search=True`），30% 的不稳定率完全可接受。

**实现细节**（`web_search.py`）：
```python
requests.post("https://html.duckduckgo.com/html/",
              data={"q": query}, timeout=15)
# 正则提取: result__a 链接 + result__snippet 摘要
# 清理 uddg= 跳转链接 → 真实 URL
# 最多返回 max_results=5 条，每条格式:
# **标题**\n真实URL\n摘要
```

**为什么用同步 `requests` 而不是异步 `httpx`**：DuckDuckGo 在国内不稳定，`requests` 阻塞 15 秒比 `httpx.AsyncClient` 超时更可控——Sync 调用会阻塞当前事件循环吗？不会，因为 `smart_search` 是在 Supervisor 汇总 Worker 结果**之后**才调用的，此时 Worker 已经全部完成，当前 event loop 没有其他异步任务在跑。

### smart_search 完整链路

不是所有请求都联网搜索。触发条件：前端传 `smart_search: true` → Supervisor summary 阶段检测到 → **在 Worker 结果汇总后、送入 SUMMARY_PROMPT 之前**，调 `web_search(user_msg)` → 结果追加到 `【联网搜索结果】` 段落 → 再一起送入 `SUPERVISOR_SUMMARY_PROMPT` 做最终整合。

降级：网络失败 → `web_search()` 返回 `""` → Supervisor 不追加任何搜索结果 → 纯 Worker 结果汇总。**不返回 500，不影响正常 RAG 回答**。

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
| `spots` | 1554 景点（坐标/等级/票价/开放时间/描述/贴士/文化） | ✅ 每次查询 |
| `foods` | 80+ 美食 | ✅ Advice Worker |
| `food_shops` | 1624 家美食店铺 | ⚠️ schema-only（ORM 已定义，无 Worker 查询） |
| `avoid_rules` | 250+ 避坑规则 | ✅ Advice Worker |
| `hard_rules` | 53 条硬规则 | ✅ Plan Worker Prompt |
| `transit_matrix` | 190,158 通勤对 | ✅ Plan Worker Prompt |
| `chat_sessions` | 会话冷备归档 | ⚠️ schema-only（ORM 已定义，无归档写入代码） |
| `user_profiles` | LTM 硬槽位（9 字段 Enum/JSON） | ⚠️ schema-only（ORM 已定义，无 finalize_prompt 注入） |
| `dlq` | 死信队列（archive / ltm_extract / notify） | ⚠️ schema-only（ORM 已定义，无写入代码） |

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

### user_profiles — LTM 硬槽位（⚠️ schema-only，无业务代码读写）

| 字段 | 类型 | Enum 取值 |
|------|------|----------|
| `group_type` | ENUM | solo / couple / family / friends / business / senior |
| `budget_level` | ENUM | budget / standard / comfort / luxury |
| `pace` | ENUM | relaxed / moderate / packed |
| `allergies_json` / `must_include_json` / `must_exclude_json` | JSON | 忌口 / 必去 / 黑名单 |
| `ltm_chunk_count` | INT | 累计 LTM 提取次数（防频繁覆盖） |

### dlq — 死信队列（⚠️ schema-only，无写入代码）

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

## 📈 数据种子精确数量

从 `backend/data/` 目录实际 CSV 文件验证：

| 文件 | 行数 | 说明 |
|------|------|------|
| `spots_seed.csv` | **1,554** | 景点主表 |
| `foods_seed.csv` | **80** | 美食种类 |
| `food_shops_seed.csv` | **1,624** | 美食店铺 |
| `avoid_rules_seed.csv` | **250** | 避坑规则 |
| `hard_rules_seed.csv` | **53** | 硬规则（R-001~R-053） |
| `transit_matrix.csv` | **190,157** | 通勤矩阵 |
| `itinerary_templates.csv` | **20** | 行程模板（⚠️ CSV 存在但 MySQL 表未创建，Plan Worker try/except 降级） |
| `query_variants.csv` | **12,605** | RAG Query Variants |

**注意**：`itinerary_templates.csv` 在 `data/augmented/` 目录下有种子文件，但 `01_init_db_create_tables.py` 没建对应 MySQL 表，Plan Worker 查询时会抛 `ProgrammingError` 被 try/except 捕获。这是一个已知的"种子有但表没建"的 gap。

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
| **鉴权** | JWT 仅在 config 预留字段，无 middleware | `/api/chat` 路由未强制 token，任何人可调用 |
| **数据新鲜度** | 种子 CSV 一次性导入 | 高德数据、票价、开放时间会变，缺少定时增量更新 |
| **前端** | Semi UI + Vite | 组件未抽离 Hook、无状态管理库（Zustand/Redux），对话历史用 localStorage |
| **测试覆盖** | 3 个 pytest 文件 | 只有 Agent / RAG / Worker 基本路径，缺少 API 集成测试 + 前端 E2E |
| **部署** | 本地运行 | 无 Dockerfile、无 CI/CD、无 HTTPS 证书 |
| **LTM** | schema-only（ORM + config 已就绪，无业务代码读写） | 用户画像硬槽位 + Milvus 向量记忆待实现 |

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
