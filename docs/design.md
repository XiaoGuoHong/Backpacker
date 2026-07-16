# SmartVoyage 智慧旅行助手系统环境配置文档

## 1. 文档说明

本文档说明 SmartVoyage MVP 的开发、测试与演示环境搭建步骤，包括依赖安装、配置项、环境变量、数据初始化与启动方式。适用于首次搭建环境与新增成员接入。

## 2. 环境要求

| 项目 | 版本要求 | 说明 |
| --- | --- | --- |
| 操作系统 | Windows 10+ / macOS 12+ / Linux (Ubuntu 22.04+) | 推荐 64 位 |
| Python | 3.11 及以上 | 需支持 asyncio |
| 包管理 | pip 23+ / uv 0.4+ | 推荐 uv 以提升安装速度 |
| Git | 2.40+ | 代码获取 |
| 数据库 | SQLite（默认）/ PostgreSQL 14+（可选） | MVP 默认 SQLite，只读场景 |

## 3. 获取代码

```bash
git clone <仓库地址> SmartVoyage
cd SmartVoyage
```

## 4. 创建与激活虚拟环境

```bash
# 使用 venv
python -m venv .venv
# Windows 激活
.venv\Scripts\activate
# macOS / Linux 激活
source .venv/bin/activate

# 或使用 uv
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

## 5. 安装依赖

项目依赖建议在根目录维护 `requirements.txt` 与 `requirements-dev.txt`。

```bash
pip install -r requirements.txt
# 开发期额外依赖
pip install -r requirements-dev.txt
```

### 5.1 核心依赖（建议）

| 依赖 | 用途 |
| --- | --- |
| fastapi | Web 框架与接口 |
| uvicorn | ASGI 服务运行 |
| pydantic / pydantic-settings | 配置与数据校验 |
| httpx | 异步 HTTP 调用第三方 API |
| openai（或兼容 SDK） | LLM 接入 |
| mcp | MCP 工具协议 SDK |
| sqlalchemy | 数据库 ORM / 只读查询 |
| python-dotenv | 环境变量加载 |
| loguru / structlog | 结构化日志 |

### 5.2 开发依赖（建议）

| 依赖 | 用途 |
| --- | --- |
| pytest | 单元与端到端测试 |
| pytest-asyncio | 异步测试 |
| ruff / flake8 | 代码静态检查 |
| black | 代码格式化 |
| httpie / curl | 接口调试 |

## 6. 配置文件

### 6.1 配置文件结构

```
.env                  # 本地环境变量（不入库，参考 .env.example）
.env.example          # 环境变量模板（入库）
config/
  settings.py         # 配置加载（pydantic-settings）
```

### 6.2 环境变量说明

复制模板并填写本地值：

```bash
cp .env.example .env
```

`.env.example` 示例：

```ini
# 基础
APP_NAME=SmartVoyage
APP_ENV=dev                # dev / test / demo / prod
LOG_LEVEL=INFO
REQUEST_TIMEOUT_SECONDS=10

# 服务
HOST=0.0.0.0
PORT=8000
API_PREFIX=/api/v1

# LLM
LLM_API_KEY=                # 不入库，本地填写
LLM_BASE_URL=               # 兼容端点，如留空使用默认
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.2

# 业务时区（用于相对日期转换）
BUSINESS_TIMEZONE=Asia/Shanghai

# 数据库（只读）
DATABASE_URL=sqlite:///./data/smartvoyage.db
DB_READONLY=true

# 数据源开关（true=尝试真实源，false=使用标记模拟工具）
USE_REAL_WEATHER=false
USE_REAL_TRAIN=false
USE_REAL_FLIGHT=false
USE_REAL_CONCERT=false

# 安全
MAX_INPUT_LENGTH=512
RATE_LIMIT_PER_MINUTE=60
```

> 所有密钥、Token、数据库凭据仅通过环境变量注入，禁止写入源码、测试数据或文档。

## 7. 数据库初始化

MVP 默认使用 SQLite，首次运行前初始化演示数据：

```bash
# 创建库表与演示数据（标记模拟数据）
python scripts/init_db.py
```

脚本应：
- 创建只读账号对应的访问视图（如使用 PostgreSQL）。
- 写入明确标记为“演示数据”的样例（天气/车次/航班/演唱会）。
- 不写入任何真实密钥或敏感信息。

## 8. MCP 工具配置

MVP 阶段 MCP Server 建议同进程部署以降低复杂度。工具注册在 `mcp/tools/` 下，每个工具声明 `name / input_schema / output_schema / timeout_ms / error_types`。

启用真实数据源时，需在 `.env` 中配置对应供应商 Key（通过环境变量，不入库）。未配置或 `USE_REAL_*` 为 `false` 时，自动切换到标记模拟工具。

## 9. 启动服务

### 9.1 本地开发启动

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问：
- API 文档：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

### 9.2 演示环境启动

```bash
APP_ENV=demo uvicorn app.main:app --host 0.0.0.0 --port 8000
```

演示环境使用模拟工具，无需第三方 Key。

## 10. 验证安装

运行健康检查与冒烟测试：

```bash
# 健康检查
curl http://localhost:8000/health

# 示例查询（天气，模拟数据）
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"text":"北京 2025-08-11 天气怎么样"}'
```

运行测试套件：

```bash
pytest -q
```

## 11. 环境隔离

| 环境 | 配置来源 | 说明 |
| --- | --- | --- |
| dev | `.env` (APP_ENV=dev) | 本地开发，可接模拟或真实源 |
| test | `pytest` 内置 fixture / `.env.test` | 使用 mock 工具，CI 自动运行 |
| demo | `.env` (APP_ENV=demo) | 对外演示，全部模拟工具 |
| prod | 安全配置系统注入 | 不依赖文件 `.env`，最小权限 |

各环境配置相互隔离，禁止在 dev/demo 配置中写入生产密钥。

## 12. 常见问题

| 问题 | 排查 |
| --- | --- |
| 启动报 `LLM_API_KEY` 缺失 | 确认 `.env` 已填写且被加载；demo 环境可忽略（走模拟） |
| 查询无结果但服务正常 | 检查 `USE_REAL_*` 与数据源 Key；demo 应走模拟工具 |
| 数据库只读报错 | 确认 `DB_READONLY=true` 且账号无写权限 |
| 中文乱码 | 确认终端与数据库均使用 UTF-8 |
| 端口被占用 | 修改 `.env` 中 `PORT` 或释放 8000 端口 |

## 13. 目录约定（建议）

```
SmartVoyage/
├── app/
│   ├── main.py            # 入口
│   ├── gateway/           # 接入网关
│   ├── orchestration/     # 编排/意图/参数
│   ├── agents/            # 调度与专业 Agent
│   ├── mcp/               # MCP 工具
│   └── config/            # 配置
├── data/                  # SQLite / 演示数据
├── docs/                  # 文档
├── scripts/               # 初始化脚本
├── tests/                 # 测试
├── requirements.txt
├── .env.example
└── README.md
```
