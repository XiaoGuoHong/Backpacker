# SmartVoyage 重构设计：chapter 13 智能旅行助手（行程规划器）

> 日期：2026-07-15
> 状态：待评审
> 关联：`docs/requirements.md`、`docs/design.md`、`docs/overview.md`、`docs/progress.md`

## 0. 背景与目标

现有 SmartVoyage 是一个「天气 / 火车 / 飞机 / 演唱会」信息查询 MVP，采用 FastAPI + 自建 A2A + MCP + orchestrator 架构、聊天式 Web UI。

本次重构目标：将其**整体转变为** Datawhale《Hello-Agents》第十三章所描述的**智能旅行行程规划器**——用户输入目的地、日期、偏好后，系统经多智能体协作生成含景点 / 酒店 / 天气的多日行程，并在前端提供地图可视化、预算计算、行程编辑与导出。

设计原则（来自已确认的范围决策）：

1. **整体重构为行程规划器**：不再保留旧的四类查询入口。
2. **沿用现有自建栈**：FastAPI + 自建 A2A + MCP + orchestrator，不引入课程 HelloAgents 框架源码。
3. **真实 + 演示回退**：高德地图、Unsplash 走真实 API（环境变量配置 Key），未配置时回退到标记「演示数据」的 mock。
4. **前端全功能**：地图可视化、预算计算、行程编辑、导出 PDF/图片、加载进度条 + 侧边导航。
5. **表单结构化输入**：前端表单采集目的地 / 日期 / 预算 / 偏好，提交后走多 Agent 编排。
6. **移除旧查询能力**：删除 train / flight / concert 的 Agent、工具、sources，保持代码整洁（weather 被新天气 Agent 复用）。
7. **A2A 显式三层（跨进程 HTTP）**：Client / Router / Server 各自独立进程，Server 经 HTTP 暴露 A2A 端点；更接近真实 A2A 协议。同时引入**独立 Amap MCP Server 进程**，被三个专业 Agent 共享（实现 chapter 13「共享 MCP 省配额/控频」）。

## 1. 总体架构

```
前端 (Vue3 SPA, web/)
  └─ POST /api/v1/plan ─▶ Gateway (校验/限流/request_id/Body 大小限制)
                                └─ Orchestrator 进程 (FastAPI)
                                      ├─ A2A Client: 并行派发 3 个任务 (HTTP)
                                      ├─ A2A Router: task_type → Agent 端点映射 + 超时
                                      └─ PlannerAgent (进程内整合 → Itinerary)
                                            └─ 可选 LLM / 规则回退
                                                  │ HTTP (A2A)
        ┌─────────────────────────────────────────────┼───────────────────────────┐
        ▼                                             ▼                          ▼
 AttractionSearchAgent                         WeatherQueryAgent           HotelAgent
 (独立 FastAPI 进程, A2A Server)             (独立 FastAPI 进程)        (独立 FastAPI 进程)
        │  MCP (Streamable HTTP)                  │                          │
        └──────────────┬──────────────────────────┴──────────────────────────┘
                       ▼
              Amap MCP Server (独立进程, 共享)
              · amap_poi_search / weather_tool / unsplash_search
              · 单例 client + 缓存 + 限速（共享 MCP 省配额）
```
- 每个专业 Agent 是独立进程，经 HTTP 暴露 A2A 端点（`POST /tasks/send` + `GET /.well-known/agent.json` Agent Card）。
- Orchestrator 内 `A2AClient` 按 `A2ARouter` 的端点映射并行调用；`A2A_TIMEOUT_MS` 控制超时。
- 三个 Agent 共用一个 **Amap MCP Server** 进程（Streamable HTTP，复用现有 `MCP_TRANSPORT=streamable-http` 机制），实现「共享 MCP」。
- `PlannerAgent` 不走 A2A，在 Orchestrator 进程内直接整合（它不调外部工具）。
- 进度：POST 后订阅 SSE `/api/v1/plan/<task_id>/events` 驱动前端进度条。

### 1.1 保留 / 移除 / 新增

| 类别 | 动作 | 内容 |
|---|---|---|
| 保留 | 框架 | FastAPI、gateway（router/middleware/validation/ratelimit/connection）、observability、core(errors/models/config)、llm client |
| 保留 | weather | `mcp/sources/weather_open_meteo.py`、`weather_qweather.py`、MCP 天气工具（被天气 Agent 复用） |
| 保留 | A2A / MCP / orchestrator 抽象 | 重构为显式三层（跨进程 HTTP） |
| 保留 | MCP Streamable HTTP 机制 | 现有 `mcp/server.py` + `_McpServerRunner` 复用为 Amap MCP Server |
| 移除 | 旧查询 | `train.py`/`flight.py`/`concert.py` 工具与 handler、`sources/http_adapter.py`(如仅被三者使用)、orchestrator 中 train/flight/concert 意图、`INTENT_SPECS` 相关项、对应前端卡片与测试 |
| 新增 | Agent 进程 | `AttractionSearchAgent`、`HotelAgent` 独立 FastAPI A2A Server（天气 Agent 复用 weather，亦为独立进程） |
| 新增 | MCP Server 进程 | `AmapMCP Server`：声明 `amap_poi_search` / `weather_tool` / `unsplash_search`，被三 Agent 共享 |
| 新增 | 接口 | `POST /api/v1/plan`、`GET /api/v1/plan/<task_id>/events`（SSE） |
| 移除 | 接口 | `POST /api/v1/query`（被 plan 取代） |

## 2. A2A 层（显式 Client / Router / Server，跨进程 HTTP）

每个专业 Agent 是**独立 FastAPI 进程**，经 HTTP 暴露 A2A 端点；Orchestrator 进程内持有 Client 与 Router。目录 `app/a2a/`：

- **`messages.py`（沿用）**：`A2ARequest` / `A2AResponse` / `A2AError`。`task_type` 取值：`attraction` / `weather` / `hotel`；Planner 不走 A2A。
- **`server.py`（Server 角色，新增）**：`A2AServer` 基类 + `create_a2a_app(server, settings)` 生成 FastAPI ASGI 应用，暴露：
  - `POST /tasks/send`：接收 `A2ARequest`，调用 `server.handle()`，返回 `A2AResponse`（含超时/异常转标准错误）。
  - `GET /.well-known/agent.json`：返回 **Agent Card**（name / task_types / 健康检查 / 能力描述），供 Router 发现与校验。
  - `GET /health`：进程内 Agent 存活 + 其 MCP 依赖可用性。
  - `SpecialistAgent`（景点/天气/酒店）继承 `A2AServer`，`handle()` 经 **MCP Client** 调 Amap MCP Server。
- **`client.py`（Client 角色，新增）**：`A2AClient` 封装 `dispatch(task_type, params, request_id)` 与 `dispatch_multi(items, request_id)`（并行 `asyncio.gather`，各自独立超时）。用 `httpx.AsyncClient` 向各 Agent 的 `/tasks/send` 发 JSON。
- **`router.py`（Router 角色，新增）**：`A2ARouter` 维护 `task_type → agent_base_url` 映射（来自 settings，可选经 Agent Card 校验）。`dispatch(request)` 解析 `task_type` → 取端点 → 经 Client 发 HTTP；未知类型、超时、连接失败统一转 `A2AResponse` 错误。状态/时延经 `log_event` 串联 `request_id`。
- **`transport.py`（精简）**：新增 `HttpA2AConnection`（封装 httpx 调用 + 超时 + 重试/连接健康），保留 `InProcessA2AConnection` 作为**测试/单机回退**（设 `A2A_TRANSPORT=in-process` 时，Agent 在 Orchestrator 进程内注册，便于单测与无多进程演示）。

进程启动方式：
- Orchestrator 进程的 `lifespan` 中复用现有 `_McpServerRunner` 思路，拉起 **Amap MCP Server** 与三个 **Agent Server** 子进程（UVICORN 线程/子进程），并等待端口就绪（健康检查轮询）；shutdown 时优雅退出。
- 亦支持独立手动启动（各自 `uvicorn app.a2a.<agent>:app --port ...`），便于调试。

调用关系（跨进程）：
```
Orchestrator 进程
  └─ A2AClient.dispatch_multi([attraction, weather, hotel])
        └─ A2ARouter: task_type → agent URL
              └─ HTTP POST agent/tasks/send
                    └─ A2AServer.handle
                          └─ MCPClient.call(tool) ──▶ Amap MCP Server (共享进程)
```

## 3. MCP 层（独立 Amap MCP Server 进程，被三 Agent 共享）

目录 `app/mcp/`，沿用 `tool.py`(ToolDefinition) / `connection.py`(`StreamableHttpMCPConnection`) / `server.py`(`build_mcp_server_app`) / `registry.py`。复用现有 **Streamable HTTP** 机制（`MCP_TRANSPORT=streamable-http` 同款）。

### 3.1 Amap MCP Server（独立进程，`app/mcp/server.py` 扩展）
- `build_amap_mcp_server(settings)`：用官方 `FastMCP` / `ClientSession` 声明下列工具，以 `stateless_http` 暴露为独立 ASGI 应用（默认端点 `/mcp`）。
- 内部单例 `AmapClient`（`mcp/sources/amap.py`）封装高德 Web 服务 REST（key 来自 `AMAP_API_KEY`）：
  - `text_search(keywords, city, type?)` → POI 列表（景点 / 酒店）
  - `weather(city)` → 天气预报
  - `direction(route_type, origin, destination)` → 路线（用于地图 polyline，可选）
- 内置 **请求缓存**（按 query 缓存，TTL 可配）+ **简单限速**（最小调用间隔 / 令牌桶）——即 chapter 13「共享 MCP 节省配额、控制调用频率」的落点；因单一进程被三 Agent 共用，天然共享。
- 无 `AMAP_API_KEY` 时相关工具返回标记 `is_demo=true` 的 mock 数据。

### 3.2 工具注册（在 Amap MCP Server 内）
| 工具 | handler | 数据源（真实 → 回退） |
|---|---|---|
| `amap_poi_search` | `make_poi_handler(mode)` | 高德 POI / demo |
| `weather_tool` | 沿用 | 高德天气 → Open-Meteo(免 Key) → demo |
| `unsplash_search` | `make_unsplash_handler(mode)` | Unsplash API / 占位图 |

- 天气 Agent 复用 `weather_tool`，优先级：高德天气（有 Key）→ Open-Meteo（免 Key）→ demo。
- `unsplash_search` 在拿到景点名后为每个景点补充 `image_url`。

### 3.3 Agent 侧 MCP 连接
- 三个 Agent Server 进程各自持有一个 `StreamableHttpMCPConnection`，指向同一个 Amap MCP Server 地址（来自 `AMAP_MCP_URL`，如 `http://127.0.0.1:8001/mcp`）。
- 沿用现有 `StreamableHttpMCPConnection`（`streamablehttp_client` + `ClientSession.call_tool`，单任务内建链/关闭）。

### 3.4 移除
删除 `mcp/tools/train.py`、`flight.py`、`concert.py` 及对应 `sources/http_adapter.py`（若仅被三者使用）；`sql/` 只读工具保留（与行程规划解耦，不影响）。

## 4. 编排层 `app/orchestrator/`

- **`params.py`**：移除旧 `INTENT_SPECS` 的 train/flight/concert；新增 `TripRequest` 参数校验（目的地非空、日期合法、天数合理、预算档位枚举、偏好列表）。
- **`service.py`**：`OrchestratorService.plan(request: TripRequest)`：
  1. 校验 `TripRequest`。
  2. 经 `A2AClient` 并行派发 `attraction` / `weather` / `hotel`。
  3. 收集响应；`attraction` 结果逐个调 `unsplash_search` 补图。
  4. 调 `PlannerAgent.integrate(...)` → 结构化 `Itinerary`。
  5. SSE 推送阶段状态（见 §5）。
  6. 返回统一响应（含 `is_demo`、来源、request_id、`notes`）。
- **`agent.py`**：`OrchestratorAgent` 改为持有 `A2AClient`；保留 `dispatch_multi`。
- **`intent.py`**：行程规划无需 NL 意图识别，移除 `RuleBasedIntentRecognizer` 对查询意图的依赖；保留可插拔 LLM 整合位（Planner 用）。
- **`session.py`**：保留会话内状态（本次规划 task_id、已生成 itinerary），支持「重新规划 / 微调」。
- **`llm/client.py`**：`LLMClient` 用于 Planner 整合（`LLMPlanner`）与可选回答生成；无 Key 时 `TemplatePlanner` 规则模板回退。

### 4.1 PlannerAgent（整合者，不走 A2A）
输入：attractions[]、hotels[]、daily_weather[]、user prefs（budget_level / interests / hotel_type / days）。
输出：`Itinerary`（逐日分配景点、匹配酒店、标注每日天气、计算预算）。
- 真实模式：LLM 按约束（预算、偏好、地理邻近）生成日计划 JSON。
- 回退模式：规则模板（按评分排序、每天 N 个景点、均匀分配）。

## 5. 数据模型（Pydantic, `app/core/models.py`）

```python
class TripRequest:
    destination: str
    start_date: date
    end_date: date | None      # 与 days 二选一
    days: int | None
    budget_level: Literal["low","mid","high"]
    interests: list[str]        # 历史文化/自然风光/美食/购物...
    hotel_type: Literal["经济型","舒适型","豪华型"]

class Attraction:
    name; address; location: GeoPoint(lng,lat); rating: float|None
    image_url: str|None; ticket_price: float|None; tags: list[str]

class Hotel:
    name; address; location: GeoPoint; price_per_night: float|None; star: int|None

class DailyWeather:
    date; day_desc; temp_min; temp_max; precipitation; wind

class ItineraryDay:
    date; index; attractions: list[Attraction]; hotel: Hotel|None; weather: DailyWeather|None

class BudgetBreakdown:
    ticket; hotel; food; transport; total; currency

class Itinerary:
    days: list[ItineraryDay]; budget: BudgetBreakdown
    notes: list[str]; is_demo: bool; sources: list[str]
```

## 6. 后端接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/plan` | 接收 `TripRequest`，返回 `task_id`；规划完成后经 SSE/轮询取结果 |
| GET | `/api/v1/plan/<task_id>/events` | SSE：推送阶段状态（"正在搜索景点…" / "正在规划行程…" / "完成"） |
| GET | `/api/v1/plan/<task_id>` | 取最终 `Itinerary`（SSE 未用时轮询） |
| GET | `/health` | 应用存活 + 依赖可用性（Amap/Unsplash/Open-Meteo） |
| GET | `/metrics` | 各 Agent 调用次数/成功率/超时/耗时 |

- 并行派发三 Agent（带 `A2A_TIMEOUT_MS`）；部分失败保留有效结果并在 `notes` 说明（补齐 chapter 13 的部分失败聚合）。
- 统一错误包装沿用 `core/errors.py`（`E_*` 错误码 + 脱敏）；演示数据明确标记。
- 敏感信息（Key/Token）不进日志与响应。

## 7. 前端（重写 `web/`，Vue3 + Vite + TS）

技术栈沿用：Vue3 + Vite + TS；交互经 SSE 订阅进度。

### 7.1 页面结构
- **表单页**：目的地、日期范围（或天数）、预算档位、兴趣偏好（多选 chips）、酒店类型 → 提交触发 `POST /api/v1/plan`。
- **加载态**：订阅 SSE 状态消息，显示**进度条 + 阶段文案**。
- **结果页**：
  - **侧边导航**：逐日列表，点击定位当日。
  - **行程卡片**：每日景点（Unsplash 图片）、当晚酒店、当日天气。
  - **地图可视化**：高德 JS API（`AMAP_JS_KEY`）标注景点 marker + 每日路线 polyline；无 JS Key 时降级为文字列表。
  - **预算面板**：门票 / 酒店 / 餐饮 / 交通明细 + 总额。
  - **行程编辑**：增删 / 拖拽排序景点 → 实时重算预算与地图。
  - **导出**：`jsPDF`（PDF）/ `html2canvas`（图片）。
- **顶栏**：健康/指标药丸（沿用现有轮询 `/health`、`/metrics`）。

### 7.2 关键文件
- `src/App.vue`：表单 + 结果布局切换。
- `src/api.ts`：封装 `plan` / SSE 订阅 / `fetchHealth` / `fetchMetrics`。
- `src/components/`：`PlanForm.vue`、`Progress.vue`、`ItineraryDay.vue`、`AttractionCard.vue`、`MapView.vue`、`BudgetPanel.vue`、`SidebarNav.vue`、`ExportBar.vue`。
- `src/types.ts`：与后端 Pydantic 模型对齐的 TS 类型。
- XSS 防护：所有文本经 Vue 插值转义，不使用 `v-html`。

## 8. 错误处理与测试

- 每 Agent 独立超时 / 降级；演示数据标记；`notes` 说明缺失部分。
- 新增单测：
  - `amap.py`：真实调用（有 Key 时）+ 无 Key 回退 + 缓存/限速。
  - `unsplash.py`：真实 + 占位回退。
  - 四个 Agent（含 Planner 整合、规则回退）。
  - 编排并行派发 + 部分失败聚合。
  - 行程编辑重算（前端以单测/类型检查覆盖，逻辑尽量下沉后端）。
- 移除 `train/flight/concert` 相关旧测试；保留并复用 gateway / A2A / MCP / SQL 安全 / 可观测性测试。
- 前端 `npm run type-check` 保持通过。
- 既有 AC-11/AC-12/AC-14（SQL 安全、脱敏、链路追踪）继续满足。

## 9. 环境与配置（`.env`）

新增 / 调整变量（均带安全默认值）：

| 变量 | 说明 | 默认 |
|---|---|---|
| `AMAP_API_KEY` | 高德 Web 服务 Key（POI/天气/路线，Amap MCP Server 用） | 无 → demo |
| `AMAP_JS_KEY` | 高德 JS API Key（前端地图） | 无 → 降级列表 |
| `UNSPLASH_ACCESS_KEY` | Unsplash 图片搜索 | 无 → 占位图 |
| `WEATHER_SOURCE` | `amap` / `open-meteo` / `demo` | `open-meteo` |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | Planner 整合用 | 无 → 规则回退 |
| `A2A_TRANSPORT` | `http`(跨进程，默认) / `in-process`(测试/单机回退) | `http` |
| `ATTRACTION_AGENT_URL` / `WEATHER_AGENT_URL` / `HOTEL_AGENT_URL` | 各 A2A Server 端点 | `http://127.0.0.1:8xx0/tasks/send` |
| `AMAP_MCP_URL` | Amap MCP Server 地址（三 Agent 共享） | `http://127.0.0.1:8001/mcp` |
| `A2A_TIMEOUT_MS` | Agent 派发超时 | `12000` |
| `AMAP_CACHE_TTL` / `AMAP_RATE_LIMIT` | Amap MCP Server 内缓存与限速 | 可配 |

## 10. 验收对照（重构后）

| 能力 | 说明 |
|---|---|
| 表单提交 → 多日行程 | 目的地/日期/偏好 → 含景点+酒店+天气 |
| 多 Agent 协作（A2A Client/Router/Server） | 景点/天气/酒店并行，Planner 整合 |
| 共享 MCP（Amap） | 单例 client + 缓存 + 限速 |
| 地图可视化 | 高德 JS API marker + 路线；无 Key 降级 |
| 预算计算 | 门票/酒店/餐饮/交通明细 |
| 行程编辑 | 增删/调序 → 实时重算 |
| 导出 | PDF / 图片 |
| 进度条 + 侧边栏 | SSE 驱动 |
| 真实 + 演示回退 | 无 Key 走 demo 并标记 |
| 安全/可观测 | 脱敏、链路日志、SQL 安全（保留） |

## 11. 实施顺序（建议，供 writing-plans 拆解）

1. 数据模型 + 移除旧 train/flight/concert。
2. Amap MCP Server 进程（POI/天气/Unsplash 工具 + 缓存/限速 + demo 回退），复用现有 Streamable HTTP 机制。
3. A2A 显式三层：Server（`create_a2a_app` + Agent Card）、Client（httpx）、Router（端点映射）+ `A2A_TRANSPORT=in-process` 回退。
4. 三个 Agent Server 进程（景点/天气/酒店，各连共享 Amap MCP）+ 进程内 PlannerAgent。
5. Orchestrator `lifespan` 拉起子进程（MCP Server + 三 Agent），`POST /plan` + SSE 进度 + 并行派发与部分失败。
6. 前端重写（表单 → 进度 → 结果：地图/预算/编辑/导出/侧边栏）。
7. 测试补齐 + type-check + 端到端演示。
