# SmartVoyage 实现进度同步

> 本文档记录 SmartVoyage MVP 截至当前的代码实现进度，作为需求文档（`requirements.md`）、技术设计文档（`design.md`）、需求分析（`overview.md`）的开发对照与验收依据。
> 最后更新：2026-07-11。技术栈：Python 3.11+ / FastAPI / Pydantic v2 / httpx；MCP 工具连接层默认同进程，亦可经官方 **Streamable HTTP** 传输（`MCP_TRANSPORT=streamable-http`，网关在 `lifespan` 拉起独立 MCP 服务，与编排服务经 HTTP 解耦）。

## 1. 总体进度

| 阶段 | 状态 |
| --- | --- |
| 网关接入连接层（gateway ↔ orchestrator） | ✅ 完成 |
| A2A 连接层（orchestrator ↔ specialist agents） | ✅ 完成 |
| MCP 工具连接层（agents ↔ tools） | ✅ 完成（支持同进程 + Streamable HTTP 传输） |
| 编排服务（意图识别 / 参数校验 / 会话 / 路由 / 汇总） | ✅ 完成 |
| 真实数据源接入（天气 Open-Meteo，其余可插拔） | ✅ 完成（天气）/ ⚠️ 其余待供应商 |
| LLM 接入（可插拔，默认规则回退） | ✅ 接口完成（默认关闭） |
| SQL 只读安全（AC-11） | ✅ 完成 |
| 可观测性（结构化链路日志 + 指标） | ✅ 完成 |
| 前端 Web 界面 | ✅ 完成（聊天式 Web UI，会话内追问/参数补充） |

**测试**：`pytest` 全量 **51 passed**（10 个测试文件，覆盖网关、A2A、MCP、MCP Streamable HTTP、编排、真实数据源、LLM、SQL 安全、可观测性、Web 入口）。

## 2. 已实现的模块与文件

### 2.1 网关接入连接层 `app/gateway/`
- `router.py`：`POST /api/v1/query`（统一查询）、`GET /health`（应用存活 + 依赖可用性）、`GET /metrics`（指标快照）。
- `connection.py`：`OrchestratorConnection` 抽象 + `InProcessOrchestratorConnection`（同进程，支持 `health_fn` 真实探测）+ `HttpOrchestratorConnection`（独立进程，超时/重试/连接健康）。
- `middleware.py`：请求 ID 注入（`X-Request-Id`）+ 请求体大小限制（413）。
- `validation.py`：输入校验（非空、512 字上限、非法字符）。
- `ratelimit.py`：按客户端 IP 的限流。
- 统一错误包装：`app/core/errors.py`（`E_*` 错误码 + 脱敏，不暴露内部细节）。

### 2.2 A2A 连接层 `app/a2a/`
- `messages.py`：`A2ARequest` / `A2AResponse`（符合设计 §4.3 结构）。
- `transport.py`：`A2AConnection` 抽象 + `InProcessA2AConnection`（未知任务类型、超时控制、结构化日志）。
- `agent.py`：`SpecialistAgent` 基类，经 MCP 调用工具并规范化结果。

### 2.3 MCP 工具连接层 `app/mcp/`
- `tool.py`：`ToolDefinition`（name/description/input_schema/output_schema/timeout_ms/error_types）+ 注册表。
- `connection.py`：`InProcessMCPConnection`（同进程，默认）+ `StreamableHttpMCPConnection`（官方 MCP **Streamable HTTP** 传输，`streamablehttp_client` + `ClientSession.call_tool`，每次调用在单任务内建链/关闭，避免跨任务取消作用域问题）。
- `server.py`：`build_mcp_server_app(settings)` 用官方 `FastMCP` 声明 `weather_tool`/`train_tool`/`flight_tool`/`concert_tool`/`db_query_tool`（复用现有 handler），以 `stateless_http` 模式暴露为独立 ASGI 应用（默认端点 `/mcp`）。
- `tools/`：`weather.py` / `train.py` / `flight.py` / `concert.py`，均暴露 `make_*_handler(mode)`：
  - 天气：`open-meteo` → 真实 Open-Meteo 接口；`qweather` → 和风天气 QWeather 接口；否则 demo（标记"演示数据"）。
  - 火车/飞机/演唱会：`real` → 通用 HTTP 适配器（按 `{PREFIX}_API_URL`/`{PREFIX}_API_KEY`）；否则 demo。
- `sources/weather_open_meteo.py`：真实天气适配器（地理编码 + 预报，WMO 代码映射为中文，过去日期返回 `date_out_of_range`）。
- `sources/weather_qweather.py`：和风天气 QWeather 适配器（城市查询 + 3 天预报，免费开发版）。
- `sources/http_adapter.py`：通用真实 HTTP 适配器，供 train/flight/concert 的 `real` 模式复用。
- `sql/validator.py` + `sql/db_tool.py`：只读 DB 工具 + SQL 安全校验（AC-11）。

### 2.4 编排服务 `app/orchestrator/`
- `intent.py`：`IntentRecognizer` 抽象 + `RuleBasedIntentRecognizer`（可插拔 LLM）。
- `params.py`：四类意图必要参数表、城市/路线/相对日期抽取。
- `session.py`：`SessionStore`，会话内参数合并（支持“改成上海”式修正，AC-06）。
- `agent.py`：`OrchestratorAgent`，按意图路由并派发 A2A。
- `service.py`：`OrchestratorService`，串联识别→校验→派发→汇总，生成回答、记录指标、结构化日志、真实 health 探测、结果数量限制（`max_results`）。
- `llm/client.py`：`LLMClient`（OpenAI 兼容 `/chat/completions`）、`LLMIntentRecognizer`、`TemplateAnswerGenerator`（无 Key 回退）、`LLMAnswerGenerator`、工厂函数。

### 2.5 可观测性 `app/observability/`
- `logging.py`：JSON 结构化日志（request_id/task_id/agent_type/tool_type/status/duration_ms/error_code），经 `contextvars` 跨层串联。
- `metrics.py`：调用次数 / 成功 / 失败 / 超时 / 平均耗时的内存指标。

### 2.6 应用入口 `app/main.py`
- `create_app(settings)`：装配中间件、路由、异常处理器、编排服务连接；`lifespan` 中初始化日志、按需拉起独立 MCP Streamable HTTP 服务（见 `MCP_TRANSPORT=streamable-http`），并关闭 HTTP 连接。

### 2.7 前端 Web 界面（Vue 3 + Vite + TypeScript）`web/`
- 技术栈：**Vue 3 + Vite + TypeScript**（组件化 SPA，独立前端工程，位于仓库 `web/`）。`npm install && npm run dev` 开发（Vite 反向代理 `/api`、`/health`、`/metrics` 到后端）；`npm run build` 产出 `web/dist`。
- 后端 `app/main.py`：若 `web/dist` 存在则经 `StaticFiles` 挂载为站点根（`/` 返回 `index.html`），API 路由（`/api`、`/health`、`/metrics`）优先匹配；未构建时回退到旧版自包含 `app/web/index.html`。
- 结构与能力：
  - `src/App.vue`：聊天式布局（顶栏健康/指标药丸、消息流、输入框），`Enter` 发送、回车换行（`shift+enter`），“新对话”重置 `session_id`。
  - `src/api.ts`：封装 `query`/`fetchHealth`/`fetchMetrics`，`session_id` 由 `localStorage` 持久化（键 `sv_session`）。
  - `src/components/MessageBubble.vue` + `ResultCard.vue` + `ValueNode.vue`（递归渲染嵌套对象/数组）。
  - 渲染统一响应：优先 `answer`，其次 `condition_summary`；结果以键值表展示（`is_demo` 标记“演示数据”徽标）；展示来源、查询时间、提示与 `request_id`。
  - 顶部状态栏每 30s 轮询 `/health` 与 `/metrics`。
  - **XSS 防护**：所有文本经 Vue 插值（自动转义），不使用 `v-html`，满足 §8.2 输出转义要求。

## 3. 运行方式

### 后端（FastAPI）
```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
pytest                 # 运行全部测试
python -m uvicorn app.main:app --port 8000   # 启动服务（API + 若已构建则托管前端 dist）
```

### 前端（Vue 3 + Vite + TS，`web/`）
```bash
cd web
npm install
npm run dev        # 开发：Vite :5173，反向代理 /api -> 后端 :8000
npm run build      # 产出 web/dist，由后端在 / 托管（生产形态）
npm run type-check # vue-tsc 类型检查
```
> 仅运行后端且未执行 `npm run build` 时，`GET /` 回退到旧版自包含 `app/web/index.html`；执行构建后由 `web/dist` 提供服务。

关键环境变量（均带安全默认值，不写源码）：

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `WEATHER_SOURCE` | 天气数据源 `open-meteo` / `qweather`(真实) / `demo` | `open-meteo` |
| `WEATHER_API_KEY` | 和风天气 QWeather API Key（`WEATHER_SOURCE=qweather` 时必填） | 无 |
| `TRAIN_SOURCE` / `FLIGHT_SOURCE` / `CONCERT_SOURCE` | 其余三类 `real` / `demo` | `demo` |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | OpenAI 兼容 LLM | 无 |
| `LLM_INTENT_ENABLED` / `LLM_ANSWER_ENABLED` | 启用 LLM 意图识别 / 回答生成 | `false` |
| `DB_ENABLED` / `DB_PATH` / `DB_ALLOWED_TABLES` / `DB_MAX_ROWS` | 只读 DB 工具（AC-11） | `false` |
| `MAX_RESULTS` | 单次返回结果数量上限（§10.1） | `20` |
| `A2A_TIMEOUT_MS` | A2A / 专业 Agent 派发超时（天气等真实联网调用需放宽） | `12000` |
| `ORCHESTRATOR_URL` | 设置后编排服务走独立进程 HTTP 连接 | 无（同进程） |
| `MCP_TRANSPORT` | MCP 传输方式 `in-process`(默认) / `streamable-http` | `in-process` |
| `MCP_HTTP_URL` | `streamable-http` 模式下的 MCP 服务地址（网关会按此地址在 lifespan 拉起独立 MCP 服务） | `http://127.0.0.1:8001/mcp` |
| `MCP_HTTP_PATH` | MCP Streamable HTTP 端点路径（需与 `MCP_HTTP_URL` 路径一致） | `/mcp` |

## 4. 验收标准（AC）覆盖对照

| 编号 | 场景 | 状态 | 说明 |
| --- | --- | --- | --- |
| 天气查询 | ✅ | 规则/LLM 识别 + 真实 Open-Meteo / QWeather 或 demo |
| AC-02 | 火车票查询 | ✅ | 结构化车次，数据源未提供余票不虚构 |
| AC-03 | 飞机票查询 | ✅ | 结构化航班 + 价格(数值+币种) |
| AC-04 | 演唱会查询 | ✅ | 结构化演出或明确无结果 |
| AC-05 | 参数缺失 | ✅ | 列出缺失项，不调用不必要工具 |
| AC-06 | 参数修改 | ✅ | 会话内合并（“改成上海”“日期换成…”）；过去依赖 `_intent` 记忆 |
| AC-07 | 意图不明确 | ✅ | 请求澄清，不随机返回 |
| AC-08 | 数据源无结果 | ✅ | 区分无数据与服务异常 |
| AC-09 | 工具超时 | ✅ | A2A/MCP 独立超时 |
| AC-10 | 部分失败 | ❌ | 尚未实现多工具并行派发 + 部分失败聚合 |
| AC-11 | SQL 安全 | ✅ | 非只读/多语句/越权表/超量执行前拦截 + 脱敏审计 |
| AC-12 | 敏感信息保护 | ✅ | 错误脱敏，日志不记录 Key/Token |
| AC-13 | 结果真实性 | ✅ | 事实字段仅来自工具返回，LLM 不补造 |
| AC-14 | 链路追踪 | ✅ | `request_id` 透传 + 结构化日志串联 |

## 5. P0 / P1 完成情况

### P0（必须）
- [x] 接入网关 + 统一查询接口
- [x] 四类意图识别与参数抽取
- [x] 参数校验与补充询问
- [x] 调度 + 专业 Agent 基础 A2A 协作
- [x] MCP 工具注册、调用、超时、错误处理
- [x] 每类查询至少一个可运行适配器或标记模拟工具
- [x] 统一响应 + 来源/查询时间
- [x] SQL 只读控制、敏感信息保护、链路日志（AC-11 / AC-12 / AC-14）
- [x] 核心自动化测试和演示流程

### P1（稳定性增强）
- [x] 会话内条件修改（参数补充/修正）
- [x] Web 入口（Vue 3 + Vite + TS 聊天式界面，§9.1；`web/dist` 由后端托管，开发态 Vite 代理）
- [x] 指标统计、依赖健康检查（已完成；契约测试待做）
- [ ] 部分失败结果返回（AC-10，多工具并行）
- [ ] 结果排序 / 筛选（数量限制已完成 `max_results`，排序/筛选待做）
- [x] 授权允许时替换真实数据源（天气已接入 Open-Meteo 与 QWeather；其余待供应商）

## 6. 待办 / 下一步
1. **AC-10 部分失败**：多 Agent 并行派发 + 失败保留有效结果并说明缺失。
2. **提示词注入专项防护与测试**（§8.2、§11.2）：当前仅做不可信校验，缺专项测试。
3. **部署**：Dockerfile / 环境隔离脚本（§10）。
4. **契约测试**：A2A 消息、MCP 工具输入输出的显式契约测试。
5. **结果排序 / 筛选**：`max_results` 已完成，排序与筛选待做。

> **最近更新（2026-07-11）**：✅ 接入和风天气 QWeather 数据源（`WEATHER_SOURCE=qweather` + `WEATHER_API_KEY`）。
