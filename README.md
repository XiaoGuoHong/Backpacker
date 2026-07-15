# Backpacker 智能旅行行程规划器

> 一个基于 FastAPI + Vue 3 + 多 Agent（A2A/MCP）协作的智能旅行行程规划器。
> 输入目的地、日期、预算与偏好，系统自动生成含景点、酒店、天气与预算的多日行程。

## 项目状态

当前处于 **MVP 阶段**，前身为 SmartVoyage，正从「天气 / 火车 / 飞机 / 演唱会」查询助手重构为 **智能旅行行程规划器**。

- 设计文档：`docs/superpowers/specs/2026-07-15-itinerary-planner-redesign-design.md`
- 需求文档：`docs/requirements.md`
- 技术设计：`docs/design.md`

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 | Python 3.11+ / FastAPI / Pydantic v2 / httpx |
| 前端 | Vue 3 / Vite / TypeScript |
| Agent 协作 | 自建 A2A（Agent-to-Agent）协议 |
| 工具协议 | MCP（Model Context Protocol） |
| 数据 | 高德地图 / Unsplash / Open-Meteo（未配置 Key 时回退到标记的演示数据） |

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/XiaoGuoHong/Backpacker.git
cd Backpacker

# 2. 安装后端依赖
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# 3. 安装前端依赖
cd web
npm install
npm run build
cd ..

# 4. 配置环境变量（复制模板后按需填写）
cp .env.example .env

# 5. 启动服务
python -m uvicorn app.main:app --port 8000
```

访问：

- Web UI：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

## 环境变量

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `AMAP_API_KEY` | 高德 Web 服务 Key（POI/天气/路线） | 无 → demo |
| `AMAP_JS_KEY` | 高德 JS API Key（前端地图） | 无 → 降级列表 |
| `UNSPLASH_ACCESS_KEY` | Unsplash 图片搜索 | 无 → 占位图 |
| `WEATHER_SOURCE` | 天气源：`amap` / `open-meteo` / `demo` | `open-meteo` |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | Planner 整合用 LLM | 无 → 规则回退 |
| `A2A_TRANSPORT` | `http`(跨进程) / `in-process`(单机回退) | `http` |
| `A2A_TIMEOUT_MS` | Agent 派发超时 | `12000` |

## MVP 范围（当前迭代）

1. 后端接口：`POST /api/v1/plan` 生成行程，`GET /api/v1/plan/<task_id>` 取结果。
2. 三个专业 Agent：景点搜索、天气查询、酒店搜索。
3. 共享 Amap MCP Server：POI 搜索、天气、Unsplash 图片。
4. PlannerAgent：整合景点/天气/酒店为多日行程。
5. 前端：结构化表单 + 结果页（景点列表、每日天气、预算）。
6. 真实 API 未配置时回退到标记的演示数据。

## 后续迭代

- 地图可视化（高德 JS API marker + 路线）
- 行程编辑（增删/拖拽排序景点）
- 导出 PDF / 图片
- SSE 进度条
- 更多真实数据源接入

## 测试

```bash
pytest
```

## 许可证

MIT
