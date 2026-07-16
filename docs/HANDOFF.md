# SmartVoyage 项目交接文档

> 最后更新：2026-07-11（P0+P1 已完成）
> 详细进度见 `docs/report.md`
> 适用对象：接手继续开发 SmartVoyage 的工程师
> 配套文档：`docs/requirements.md`（需求）、`docs/design.md`（设计）、`docs/overview.md`（分析）、`docs/progress.md`（实现进度）

---

## 1. 项目是什么

SmartVoyage 是一个**分层多 Agent 智慧旅行助手**：用户用自然语言提问（天气 / 火车票 / 飞机票 / 演唱会），系统做意图识别 → 参数抽取 → 编排路由 → 调用专业 Agent → 通过 MCP 调用工具（真实/模拟数据源）→ 汇总回答。

四层结构（均为 FastAPI/Python，MVP 同进程；MCP 可选独立进程 Streamable HTTP）：

```
用户 → 网关 Gateway → 编排 Orchestrator → A2A → 专业 Agent → MCP → 工具/数据源
```

三类意图参数：`weather`/`concert` 需要 `city`+`date`；`train`/`flight` 需要 `from`+`to`+`date`。

---

## 2. 技术栈与环境

- **语言**：Python 3.11+（开发环境实测 **Python 3.14.4 / Windows**）
- **后端**：FastAPI + Pydantic v2 + httpx + uvicorn
- **前端**：**Vue 3 + Vite + TypeScript**（独立工程，位于 `web/`）
- **MCP SDK**：官方 `mcp>=1.0`（FastMCP + `streamablehttp_client`）
- **Node**：实测 v24（前端构建用）
- **测试**：pytest（51 个用例全绿）

依赖入口：后端 `requirements.txt`，前端 `web/package.json`。

---

## 3. 目录结构速览

```
app/
  main.py                  # FastAPI 装配入口（create_app），lifespan 拉起 MCP 服务、托管前端 dist
  core/                  # config(Settings+环境变量) / errors(统一错误码脱敏) / models
  gateway/               # router(POST /api/v1/query, GET /health, /metrics) / middleware / validation / ratelimit / connection
  a2a/                  # messages / transport(InProcessA2AConnection) / agent(SpecialistAgent)
  mcp/
    tool.py               # ToolDefinition + 注册表
    connection.py          # InProcessMCPConnection / StreamableHttpMCPConnection
    server.py             # build_mcp_server_app：FastMCP 暴露 5 个工具（Streamable HTTP）
    tools/                # weather/train/flight/concert（make_*_handler(mode)）+ registry
    sources/              # weather_open_meteo.py（真实）/ http_adapter.py（通用 real 适配器）
    sql/                 # validator(只读校验 AC-11) / db_tool
  orchestrator/          # intent(规则/LLM) / params(城市·日期·路线抽取) / session / agent / service / llm/client
  observability/         # logging(JSON 结构化+contextvars 串联) / metrics(内存指标)
  web/
    index.html           # 旧版自包含前端（未构建前端时由后端回退提供）
web/                      # 新前端 Vue3+Vite+TS 工程（见 §5）
docs/                     # 需求/设计/分析/进度
tests/                    # 10 个测试文件，覆盖各层 + MCP Streamable HTTP
```

---

## 4. 已完成（详见 `docs/progress.md`）

- 网关接入连接层（含统一错误码脱敏、限流、请求体大小限制）
- A2A 连接层（超时 / 未知任务 / 结构化日志）
- MCP 工具连接层：**同进程 + Streamable HTTP 双模式**
- 编排服务（规则意图识别 / 参数校验 / 会话记忆 / 路由派发 / 汇总 / 指标）
- 真实数据源：**天气 = Open-Meteo（真实）**；火车/飞机/演唱会 = 可插拔（默认 demo）
- LLM 接入（OpenAI 兼容，可插拔，默认关闭）
- SQL 只读安全（AC-11）
- 可观测性（结构化链路日志 + 指标）
- 前端：**Vue 3 + Vite + TS**（聊天式 Web UI）
- 验收 AC-01~AC-09、AC-11~AC-14 覆盖；**AC-10（多工具并行部分失败）未做**
- 测试 **51 passed**

---

## 5. 如何运行

### 5.1 后端
```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
pytest                              # 全量测试（应 51 passed）
python -m uvicorn app.main:app --port 8000   # 启动
```
- `GET /`：已 `npm run build` 时返回 Vue `web/dist`；否则回退旧版 `app/web/index.html`
- `POST /api/v1/query`：`{"raw_input": "...", "session_id": "..."}`
- `GET /health`、`GET /metrics`

### 5.2 前端（Vue3 + Vite + TS，`web/`）
```bash
cd web
npm install
npm run dev          # 开发：:5173，Vite 反向代理 /api /health /metrics → 后端 :8000
npm run build        # 产出 web/dist，由后端在 / 托管（生产形态）
npm run type-check   # vue-tsc 类型检查
```

### 5.3 MCP 传输模式
- 默认 `MCP_TRANSPORT=in-process`（同进程，最快、最稳）
- `MCP_TRANSPORT=streamable-http`：后端 `lifespan` 按 `MCP_HTTP_URL`（默认 `http://127.0.0.1:8001/mcp`）**拉起独立 uvicorn 进程**提供 MCP 服务，编排层经 HTTP 调用
- `streamable-http` 模式有专门的端到端测试（`tests/test_mcp_streamable_http.py`）

---

## 6. ⚠️ 关键坑 / 注意事项（务必先看，避免重蹈覆辙）

1. **改完代码必须重启 uvicorn**。本环境曾出现“改了不生效”——日志里超时仍是旧的 5.013s，实为旧进程未重启。**任何配置/代码改动后先 Ctrl+C 重启服务。**

2. **MCP 不能 mount 到 FastAPI 下**。FastMCP 的 `streamable_http_app` 用了 anyio TaskGroup，其生命周期与任务绑定；若用 `app.mount("/mcp", mcp_app)` 会报 `Task group is not initialized`。当前方案是**独立 uvicorn 进程**（`app/main.py` 的 `_McpServerRunner`），不要改回 mount。

3. **A2A 超时**：默认 `A2A_TIMEOUT_MS=12000`（早期 5000 太短，真实天气两次外网请求叠加易超时）。Open-Meteo 在本开发环境**网络偏慢/偶发不可达**（单次约 2~4s，叠加超 5s）。

4. **天气历史日期无数据**：Open-Meteo 只支持今天及未来，过去日期返回 `date_out_of_range`。原模板会把缺失字段渲染成 `None`（如“气温 None~None°C”），现已在 `app/llm/client.py:TemplateAnswerGenerator` 中处理为友好提示（“暂无天气数据（date_out_of_range）”）。

5. **城市识别已泛化**：`app/orchestrator/params.py:extract_cities` 原先是写死的城市列表（玉林等小城识别不到），现改为提取任意中文城市名（2~4 字）。改城市相关逻辑时注意保持“从 X 到 Y”“X 飞 Y”的路线抽取仍可用。

6. **Streamable HTTP 客户端**：`StreamableHttpMCPConnection` 每次调用在**单个任务内**建立/关闭 `streamablehttp_client` 连接（不要跨任务持有 session，否则报 `asynchronous generator is already running`）。

7. **前端 XSS**：Vue 文本插值自动转义，禁止在组件里用 `v-html`。

---

## 7. 待办清单（接手人按优先级）

### ✅ P0（已完成）
**接入「和风天气 QWeather」作为天气数据源** ✅ 已实现
- 新增 `app/mcp/sources/weather_qweather.py`：城市查询 + 3 天预报（免费开发版）
- `app/core/config.py`：新增 `weather_api_key`（env `WEATHER_API_KEY`）、`weather_api_url`（env `WEATHER_API_URL`）
- `app/mcp/tools/weather.py`：`make_weather_handler` 增加 `"qweather"` 分支
- 错误处理：缺失 Key → `missing_api_key`；城市未找到 → `city_not_found`；日期超 3 天范围 → `date_out_of_range`
- 使用方式：`set WEATHER_SOURCE=qweather && set WEATHER_API_KEY=<你的Key>`
- 已添加单元测试（`tests/test_sources.py`）覆盖正常/缺Key/城市不存在/日期超范围/Handler路由

### 🟠 P1（已完成）
- [x] **AC-10 部分失败**：多 Agent 并行派发 + 失败保留有效结果并说明缺失 ✅
- [x] **提示词注入专项防护与测试** ✅（`app/gateway/security.py` + 27 测试）
- [x] **契约测试**：A2A 消息、MCP 工具输入输出的显式契约测试 ✅（23 测试）
- [x] **结果排序 / 筛选**：已完成（`_sort_results`）
- [x] **部署**：Dockerfile 多阶段构建 ✅
- [ ] **火车/飞机/演唱会真实数据源**：待供应商（已有通用 `sources/http_adapter.py` 可按 `{PREFIX}_API_URL/_API_KEY` 接入）

### 🟢 P2
- [ ] LLM 意图识别 / 回答生成默认关闭，可接 OpenAI 兼容服务（`LLM_API_KEY` 等）
- [ ] 前端可加：历史消息持久化、加载态动画、错误重试

---

## 8. 关键文件索引（改对应功能先读这里）

| 功能 | 文件 |
|---|---|
| 启动装配 / MCP 拉起 / 前端托管 | `app/main.py` |
| 配置与所有环境变量 | `app/core/config.py` |
| 统一查询接口 / health / metrics | `app/gateway/router.py` |
| 意图识别（规则） | `app/orchestrator/intent.py` |
| 参数抽取（城市/日期/路线，含今天·明天·后天） | `app/orchestrator/params.py` |
| 回答模板（None 防护在这） | `app/llm/client.py` |
| 天气 handler 选择 | `app/mcp/tools/weather.py` |
| 天气真实源（QWeather） | `app/mcp/sources/weather_qweather.py` |
| 通用真实 HTTP 适配器（train/flight/concert） | `app/mcp/sources/http_adapter.py` |
| MCP 双传输连接 | `app/mcp/connection.py` |
| MCP Streamable HTTP 服务 | `app/mcp/server.py` |
| A2A 超时 | `app/orchestrator/service.py` + `app/a2a/transport.py` |
| 前端 SPA | `web/src/App.vue`、`web/src/api.ts`、`web/src/components/*` |

---

## 9. 当前状态

- ✅ **P0+P1 已完成**，107 测试全部通过。
- QWeather 接入，`WEATHER_SOURCE=qweather` + `.env` 自动加载。
- 多意图并行派发、注入防护、契约测试、Docker 部署均已就绪。
- 仅剩 P2 锦上添花（LLM 开启、前端增强）。
- 详细报告见 `docs/report.md`。
