# 简历项目经历 · Demo

> 基于「蓉游智体 · PandaAgent」项目文档撰写，适用于 AI Agent / LLM 应用研发岗位简历。

---

## 🐼 蓉游智体 · PandaAgent｜AI Agent 全栈开发

**项目时间：** 2026.08 — 2026.09（4 周）
**项目角色：** 独立开发 / 全栈
**项目链接：** github.com/你的用户名/chengdu-travel-agent

### 项目描述

「蓉游智体 · PandaAgent」是面向秋招 AI Agent 岗位独立设计并实现的成都专属旅游智能体，覆盖「问答咨询 → 分天行程规划 → 六维出行建议 → 周边推荐」全链路闭环，并支持跨重启/跨新会话的长期用户画像记忆（如"不吃辣""亲子家庭""预算5K"等偏好自动复用）。后端基于 FastAPI + LangChain DeepAgents 多智能体架构，前端 React + Semi UI，RAG 混合检索 + 四层分层记忆系统，全链路接入 LangSmith 可观测性追踪。

### 技术栈

LangChain · **LangGraph** · LlamaIndex · **Milvus** · MySQL · **Redis** · DeepSeek · **LangSmith** · FastAPI（SSE）· React

### 核心工作与成果

1. **DeepAgents 多智能体协作架构**：采用 LangChain 官方 `create_deep_agent()` 构建主 Agent，基于用户意图自动委派 4 个 SubAgent（RAG 问答 / 硬规则行程 / 六维建议 / 周边 KNN），各 SubAgent 独立 Prompt + 专属工具；利用 DeepAgents 内置 TodoList 任务规划与上下文压缩，替代手写 LangGraph 7 节点 StateGraph，**核心代码量从 1500 行压缩至约 200 行**。

2. **四层分层记忆系统（核心卖点）**：
   - **L1 运行态**：LangGraph Checkpointer 可插拔工厂，默认 SqliteSaver（SQLite3 单文件）实现**跨进程/跨重启真持久化**，一行环境变量即可切换 MemorySaver / RedisSaver / PostgresSaver，业务代码零改动；
   - **L2 加速层**：Redis 缓存近 1 小时活跃会话 checkpoint（TTL 1h）+ LLM 语义响应缓存，明确区分"真源 vs 加速层"避免多真源写入错乱；
   - **L3 上下文压缩**：Rolling Summary 机制，消息超阈值自动摘要，控制 Token 窗口；
   - **L4 长期画像 LTM**：MySQL `user_profiles` 结构化三槽位（画像/忌口/黑名单）+ Milvus `user_ltm_v1` 向量语义 Top3 软召回（0.92 阈值去重），实现**新 session 仍可复用历史偏好**。

3. **RAG 混合检索引擎**：BGE-large-zh-v1.5 本地向量化（1024 维），Milvus Lite 零服务端本地文件存储，IVF_FLAT 索引 + 标量过滤 + jieba/BM25 软重排三阶段检索；构建 35+ 景点 / 40 美食 / 40 避坑规则知识库，**核心景点 Top1 召回率 100%**。

4. **Agent 可靠性设计**：8 条成都硬规则（如熊猫基地必须 Day1 上午）以 Python 硬编码程序级强制 + Plan Worker Prompt 注入双保险，防止 LLM 自由生成导致行程常识错误；finalize_prompt 唯一收口，杜绝"检索到了但没喂进模型"。

5. **全链路可观测性**：零代码侵入接入 LangSmith（仅环境变量），自动追踪每次 LLM 调用 / 工具调用 / SubAgent 委派链路，LangSmith Studio 可视化回放执行图谱，支持在线评测与 Prompt 版本管理。

6. **前后端工程化交付**：FastAPI SSE 流式响应实现 Token 级渐进渲染 + 结构化卡片（PlanCard/AdvicePanel/NearbyList）先于完整答案推送，**首屏感知延迟降低约 60%**；React + Semi UI 结构化展示；Pydantic 类型校验 + Loguru 分级日志；一键启动脚本，本地双击 5 秒进入演示。

### 可量化成果

- RAG 检索：核心景点 Top1 召回率 **100%**（20 条 Query 评测）
- 工程效率：多智能体核心代码量 **1500 行 → 约 200 行**（压缩 85%+）
- 体验指标：SSE 流式渲染首屏延迟降低约 **60%**
- 可靠性：8 条硬规则 100% 程序级强制，熊猫基地行程零错位
- 记忆能力：关进程重启后会话状态完整恢复，跨新会话偏好复用率覆盖画像/忌口/黑名单三槽位

---

### 💡 使用说明（替换占位符）

1. `github.com/你的用户名/chengdu-travel-agent` → 替换为真实 GitHub 仓库链接
2. 项目时间 → 按实际开发周期调整
3. 投递不同岗位时可调整重心：
   - **偏 Agent 编排岗**：突出 DeepAgents 多智能体 + LangGraph Checkpointer + 记忆分层
   - **偏 RAG 岗**：突出 Milvus + BGE + BM25 混合检索 + 召回率指标
   - **偏后端/全栈岗**：突出 FastAPI SSE + MySQL + Redis + 工程化交付
