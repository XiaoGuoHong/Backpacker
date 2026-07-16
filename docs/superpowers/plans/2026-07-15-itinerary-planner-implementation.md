# Backpacker 智能行程规划器实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or inline implementation task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 SmartVoyage 查询助手按 `docs/superpowers/specs/2026-07-15-itinerary-planner-redesign-design.md` 重构为 Backpacker 智能行程规划器，实现后端 Amap MCP Server + A2A 三层 + Planner + 前端表单/地图/预算/编辑/导出。

**Architecture:** FastAPI 后端；Orchestrator 通过 A2A Client/Router 并行派发景点/天气/酒店三个独立 Agent Server；三 Agent 共享 Amap MCP Server（POI/天气/Unsplash）；PlannerAgent 进程内整合为 Itinerary；前端 Vue3 SPA 经 SSE 订阅进度，展示地图、预算、编辑与导出。

**Tech Stack:** Python 3.11+ / FastAPI / Pydantic v2 / httpx / uvicorn / MCP / Vue3 / Vite / TypeScript

## Global Constraints

- 遵循现有代码风格，复用 gateway middleware/ratelimit、observability、core/errors、MCP connection 等可复用组件。
- 密钥仅通过环境变量注入，禁止写入源码、测试、文档。
- 真实 API 未配置时回退到明确标记 `is_demo=true` 的演示数据。
- A2A 支持跨进程 HTTP（默认）与 in-process（测试回退）。
- 日志不得记录 API Key、Token、凭据；错误响应脱敏。
- 前端文本经 Vue 插值自动转义，禁用 `v-html`。

---

## Phase 1: 基础模型与配置

### Task 1.1: 更新 `app/core/models.py`

**Files:**
- Modify: `app/core/models.py`
- Test: `tests/test_contracts.py`

**Interfaces:**
- Consumes: 无
- Produces: `TripRequest`, `GeoPoint`, `Attraction`, `Hotel`, `DailyWeather`, `ItineraryDay`, `BudgetBreakdown`, `Itinerary`, `HealthResponse`, `DependencyHealth`

- [ ] **Step 1: 编写 TripRequest / Itinerary 相关模型的契约测试**

```python
def test_trip_request_valid():
    req = TripRequest(destination="北京", start_date=date(2025, 8, 11), days=3, budget_level="mid", interests=["历史文化"], hotel_type="舒适型")
    assert req.destination == "北京"
    assert req.days == 3
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_contracts.py::test_trip_request_valid -v`
Expected: FAIL

- [ ] **Step 3: 实现模型**

定义上述 Pydantic 模型，包含字段校验（destination 非空、days 在 1-30、budget_level enum、interests 非空等）。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_contracts.py -v`
Expected: PASS

---

### Task 1.2: 更新 `app/core/config.py`

**Files:**
- Modify: `app/core/config.py`
- Reference: `.env.example`

**Interfaces:**
- Produces: `Settings` 新增 AMAP_API_KEY、AMAP_JS_KEY、UNSPLASH_ACCESS_KEY、A2A_TRANSPORT、*_AGENT_URL、AMAP_MCP_URL、AMAP_CACHE_TTL、AMAP_RATE_LIMIT；移除 train/flight/concert 相关配置。

- [ ] **Step 1: 对照 `.env.example` 更新 Settings 字段**
- [ ] **Step 2: 运行 `python -c "from app.core.config import get_settings; print(get_settings())"` 确认加载无报错**

---

### Task 1.3: 扩展错误码（如需要）

**Files:**
- Modify: `app/core/errors.py`（仅在现有错误码不足时）

- [ ] **Step 1: 检查是否需要新增 `E_PLAN_FAILED` 等错误码**
- [ ] **Step 2: 如需则添加，否则保留现有错误码体系**

---

## Phase 2: Amap MCP Server

### Task 2.1: 实现 `app/mcp/sources/amap.py`

**Files:**
- Create: `app/mcp/sources/amap.py`
- Test: `tests/test_amap.py`

**Interfaces:**
- Produces: `AmapClient`（单例）、`text_search(keywords, city, type=None) -> list[dict]`、`weather(city) -> dict`、`direction(route_type, origin, destination) -> dict`
- 内置缓存（`AMAP_CACHE_TTL`）与限速（`AMAP_RATE_LIMIT`）。
- 无 `AMAP_API_KEY` 时返回 demo 数据。

- [ ] **Step 1: 编写 AmapClient 无 Key 回退测试**
- [ ] **Step 2: 实现 AmapClient 封装高德 REST API、缓存、限速、demo 回退**
- [ ] **Step 3: 运行 `pytest tests/test_amap.py -v`**

---

### Task 2.2: 实现 `app/mcp/sources/unsplash.py`

**Files:**
- Create: `app/mcp/sources/unsplash.py`
- Test: `tests/test_unsplash.py`

**Interfaces:**
- Produces: `UnsplashClient.search(query) -> dict`（含 image_url，无 Key 时返回占位图）

- [ ] **Step 1: 编写占位图回退测试**
- [ ] **Step 2: 实现 UnsplashClient**
- [ ] **Step 3: 运行 `pytest tests/test_unsplash.py -v`**

---

### Task 2.3: 更新 `weather_tool` 支持多日/Amap

**Files:**
- Modify: `app/mcp/tools/weather.py`
- Test: `tests/test_mcp.py`

**Interfaces:**
- Consumes: `AmapClient.weather`, `weather_open_meteo`, `weather_qweather`
- Produces: `weather_tool` 输出 `DailyWeather` 列表；优先级 Amap → Open-Meteo → demo。

- [ ] **Step 1: 修改 weather handler 支持 city + days 参数**
- [ ] **Step 2: 添加 Amap 天气分支**
- [ ] **Step 3: 更新测试**

---

### Task 2.4: 新建 POI / Unsplash MCP 工具

**Files:**
- Create: `app/mcp/tools/amap_poi_search.py`
- Create: `app/mcp/tools/unsplash_search.py`
- Modify: `app/mcp/tools/registry.py`
- Test: `tests/test_mcp.py`

**Interfaces:**
- Produces: `amap_poi_search` ToolDefinition + handler；`unsplash_search` ToolDefinition + handler。

- [ ] **Step 1: 实现 amap_poi_search 工具（景点/酒店）**
- [ ] **Step 2: 实现 unsplash_search 工具**
- [ ] **Step 3: 更新 registry 注册新工具并移除 train/flight/concert**
- [ ] **Step 4: 运行相关测试**

---

### Task 2.5: 重构 `app/mcp/server.py` 为 Amap MCP Server

**Files:**
- Modify: `app/mcp/server.py`
- Test: `tests/test_mcp_streamable_http.py`

**Interfaces:**
- Produces: `build_amap_mcp_server(settings)` 返回 FastMCP 实例，注册 `amap_poi_search` / `weather_tool` / `unsplash_search`。

- [ ] **Step 1: 移除 train/flight/concert 工具注册**
- [ ] **Step 2: 新增 build_amap_mcp_server**
- [ ] **Step 3: 更新 streamable HTTP server 入口使用 Amap MCP Server**
- [ ] **Step 4: 运行 streamable HTTP 测试**

---

## Phase 3: A2A 显式三层

### Task 3.1: 实现 `app/a2a/server.py`

**Files:**
- Create: `app/a2a/server.py`
- Test: `tests/test_a2a.py`

**Interfaces:**
- Produces: `A2AServer` 基类（`handle(request: A2ARequest) -> A2AResponse`）；`create_a2a_app(server, settings)` 暴露 `POST /tasks/send`、`GET /.well-known/agent.json`、`GET /health`。

- [ ] **Step 1: 编写 A2AServer 契约测试**
- [ ] **Step 2: 实现 create_a2a_app**
- [ ] **Step 3: 运行测试**

---

### Task 3.2: 实现 `app/a2a/client.py` 与 `app/a2a/router.py`

**Files:**
- Create: `app/a2a/client.py`
- Create: `app/a2a/router.py`
- Modify: `app/a2a/transport.py`（新增 HttpA2AConnection）
- Test: `tests/test_a2a.py`

**Interfaces:**
- Produces: `A2AClient.dispatch(task_type, params, request_id)`、`dispatch_multi(items, request_id)`；`A2ARouter` task_type → URL 映射；`HttpA2AConnection`。

- [ ] **Step 1: 实现 HttpA2AConnection**
- [ ] **Step 2: 实现 A2ARouter**
- [ ] **Step 3: 实现 A2AClient（基于 httpx + router）**
- [ ] **Step 4: 运行测试**

---

### Task 3.3: 调整 `app/a2a/agent.py` 为 Agent Server handler

**Files:**
- Modify: `app/a2a/agent.py`

**Interfaces:**
- Produces: `AttractionSearchAgent` / `WeatherQueryAgent` / `HotelAgent` 可继承的 `SpecialistAgent` 基类，内部通过 `StreamableHttpMCPConnection` 调 Amap MCP Server。

- [ ] **Step 1: 调整 SpecialistAgent 适配新 task_type 与 MCP 连接**
- [ ] **Step 2: 实现三个 Agent 类（或工厂）**

---

## Phase 4: 编排与规划

### Task 4.1: 实现 `app/orchestrator/planner.py`

**Files:**
- Create: `app/orchestrator/planner.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `Attraction[]`, `Hotel[]`, `DailyWeather[]`, `TripRequest`
- Produces: `Itinerary`

- [ ] **Step 1: 实现 `TemplatePlanner`（规则回退）**
- [ ] **Step 2: 实现 `LLMPlanner`（调用 LLMClient，无 Key 时回退到 TemplatePlanner）**
- [ ] **Step 3: 实现 `PlannerAgent.integrate(...)` 统一入口**
- [ ] **Step 4: 运行测试**

---

### Task 4.2: 重写 `app/orchestrator/service.py` 与 `agent.py`

**Files:**
- Modify: `app/orchestrator/service.py`
- Modify: `app/orchestrator/agent.py`
- Modify: `app/orchestrator/params.py`
- Modify: `app/orchestrator/session.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Produces: `OrchestratorService.plan(request: TripRequest) -> dict`（返回 task_id）；SSE 事件推送；并行派发 attraction/weather/hotel；部分失败聚合。

- [ ] **Step 1: 重写 params.py 为 TripRequest 校验**
- [ ] **Step 2: 扩展 session.py 存储 itinerary 与 task_id**
- [ ] **Step 3: OrchestratorAgent 改用 A2AClient**
- [ ] **Step 4: 实现 plan()：校验 → 并行派发 → unsplash 补图 → Planner 整合 → 返回 task_id**
- [ ] **Step 5: 实现 SSE events 与结果轮询**
- [ ] **Step 6: 运行测试**

---

### Task 4.3: 更新 `app/llm/client.py`

**Files:**
- Modify: `app/llm/client.py`

**Interfaces:**
- Produces: `LLMPlanner` 用于 PlannerAgent；移除旧的 `LLMIntentRecognizer` / `AnswerGenerator`。

- [ ] **Step 1: 保留 LLMClient**
- [ ] **Step 2: 新增 LLMPlanner**
- [ ] **Step 3: 移除或注释旧意图识别/回答生成代码**

---

## Phase 5: 网关与主入口

### Task 5.1: 重写 `app/gateway/router.py`

**Files:**
- Modify: `app/gateway/router.py`
- Modify: `app/gateway/validation.py`
- Remove: `app/gateway/connection.py`（如不再需要）
- Test: `tests/test_gateway.py`

**Interfaces:**
- Produces: `POST /api/v1/plan`、`GET /api/v1/plan/<task_id>/events`（SSE）、`GET /api/v1/plan/<task_id>`、`GET /health`、`GET /metrics`。

- [ ] **Step 1: 移除 POST /api/v1/query**
- [ ] **Step 2: 新增 POST /api/v1/plan**
- [ ] **Step 3: 新增 SSE /events 与 GET /plan/<task_id>`
- [ ] **Step 4: 更新 validation.py 校验 TripRequest**
- [ ] **Step 5: 运行测试**

---

### Task 5.2: 更新 `app/main.py`

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Produces: FastAPI app；lifespan 中拉起 Amap MCP Server + 三个 Agent Server 子进程（HTTP 模式）或 in-process 注册；shutdown 优雅退出。

- [ ] **Step 1: lifespan 启动 Amap MCP Server 子进程**
- [ ] **Step 2: lifespan 启动 AttractionSearchAgent / WeatherQueryAgent / HotelAgent 子进程**
- [ ] **Step 3: 等待端口健康检查就绪**
- [ ] **Step 4: shutdown 优雅关闭子进程**
- [ ] **Step 5: 挂载新 gateway router**
- [ ] **Step 6: 本地启动验证 `python -m uvicorn app.main:app --port 8000`**

---

## Phase 6: 测试与清理

### Task 6.1: 移除旧代码

**Files:**
- Remove: `app/mcp/tools/train.py`, `flight.py`, `concert.py`
- Remove: `app/mcp/sources/http_adapter.py`
- Remove: `app/orchestrator/intent.py`
- Remove: `app/gateway/connection.py`（确认不再使用）
- Remove/Update: `app/debug.py`
- Update: `tests/test_contracts.py`, `tests/test_mcp.py`, `tests/test_gateway.py`, `tests/test_orchestrator.py`, `tests/test_llm.py`

- [ ] **Step 1: 删除已移除的源码文件**
- [ ] **Step 2: 删除或重写引用旧功能的测试**
- [ ] **Step 3: 运行 `pytest -q` 确认全量通过**

---

## Phase 7: 前端重写

### Task 7.1: 更新前端依赖与类型

**Files:**
- Modify: `web/package.json`
- Create/Modify: `web/src/types.ts`

- [ ] **Step 1: 添加 @amap/amap-jsapi-loader、jspdf、html2canvas 等依赖**
- [ ] **Step 2: 定义 TripRequest / Itinerary 等 TS 类型**

---

### Task 7.2: 更新 `web/src/api.ts`

**Files:**
- Modify: `web/src/api.ts`

**Interfaces:**
- Produces: `plan(request)`、`subscribeEvents(taskId)`、`fetchItinerary(taskId)`、`fetchHealth()`、`fetchMetrics()`。

- [ ] **Step 1: 实现新 API 封装**
- [ ] **Step 2: 实现 SSE 订阅**

---

### Task 7.3: 重写 `web/src/App.vue` 与组件

**Files:**
- Modify: `web/src/App.vue`
- Create: `web/src/components/PlanForm.vue`, `Progress.vue`, `ItineraryDay.vue`, `AttractionCard.vue`, `MapView.vue`, `BudgetPanel.vue`, `SidebarNav.vue`, `ExportBar.vue`
- Remove: `web/src/components/MessageBubble.vue`, `ResultCard.vue`, `ValueNode.vue`

- [ ] **Step 1: 实现 PlanForm 表单**
- [ ] **Step 2: 实现 Progress 进度条**
- [ ] **Step 3: 实现 ItineraryDay / AttractionCard**
- [ ] **Step 4: 实现 MapView（高德 JS API，无 Key 降级）**
- [ ] **Step 5: 实现 BudgetPanel**
- [ ] **Step 6: 实现 SidebarNav / ExportBar**
- [ ] **Step 7: 组装 App.vue**
- [ ] **Step 8: 运行 `npm run type-check` 与 `npm run build`**

---

## Phase 8: 集成验证

### Task 8.1: 端到端验证

- [ ] **Step 1: 后端启动：`python -m uvicorn app.main:app --port 8000`**
- [ ] **Step 2: 健康检查：`curl http://localhost:8000/health`**
- [ ] **Step 3: POST plan 并 SSE 取结果**
- [ ] **Step 4: 前端 `npm run dev` 验证表单 → 结果完整链路**
- [ ] **Step 5: 运行 `pytest -q` 全量通过**

---

## Spec Coverage Self-Review

| 设计章节 | 覆盖任务 |
|---|---|
| 数据模型 §5 | Task 1.1 |
| Amap MCP Server §3 | Task 2.1–2.5 |
| A2A 显式三层 §2 | Task 3.1–3.3 |
| 专业 Agent / Planner §4 | Task 3.3, 4.1 |
| 编排 plan() / SSE §4, §6 | Task 4.2 |
| 网关接口 §6 | Task 5.1 |
| lifespan 子进程 §2 | Task 5.2 |
| 前端 §7 | Task 7.1–7.3 |
| 测试 §8 | Task 6.1, 各任务测试步骤 |

## Placeholder Scan

- 无 TBD / TODO / "implement later" / "similar to Task N"。
- 每个任务均指定文件路径、接口、可运行命令。
