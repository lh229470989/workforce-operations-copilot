# 本地运行与调试

## 当前运行方式

当前 `http://localhost:3000` 是由 Docker Desktop 中的 Docker Compose 栈提供的，
属于本机容器化运行，不是部署到公网。三个容器分别运行 Web、AI API 和 Demo
Core API，SQLite 数据保存在 Docker named volumes 中。

```bash
docker compose ps
docker compose logs -f ai-api
docker compose logs -f demo-core-api
docker compose logs -f web
```

容器镜像没有挂载源代码。修改代码后需要重建对应服务：

```bash
docker compose up --build -d ai-api web
```

若 Core API 也有改动，则直接重建整个栈：

```bash
docker compose up --build -d
```

## 推荐的日常调试方式

日常开发推荐停止容器，分别在三个终端中运行服务。FastAPI 和 Next.js 都会监听
代码变化，无需每次重建镜像。

```bash
docker compose down
```

终端 1，启动 Core API：

```bash
cd services/demo-core-api
source .venv/bin/activate
uvicorn app.main:app --reload --port 8001
```

终端 2，启动 AI API。根目录 `.env` 保存模型配置，先将其加载到当前终端环境：

```bash
cd services/ai-api
source .venv/bin/activate
set -a
source ../../.env
set +a
uvicorn app.main:app --reload --port 8000
```

终端 3，启动 Web：

```bash
cd apps/web
npm run dev
```

随后访问：

- Web：`http://localhost:3000`
- AI API 文档：`http://localhost:8000/docs`
- Core API 文档：`http://localhost:8001/docs`

## 只调试一个服务

也可以让 Core API 继续运行在 Docker 中，只在本机调试 AI API 和 Web：

```bash
docker compose stop ai-api web
cd services/ai-api
source .venv/bin/activate
set -a
source ../../.env
set +a
uvicorn app.main:app --reload --port 8000
```

另开终端运行 `cd apps/web && npm run dev`。此时本机 AI API 会使用默认的
`http://localhost:8001` 访问容器里的 Core API。

## 断点与诊断

- Python 可以在 VS Code/Codex 终端使用 `debugpy`，或先用日志和单测定位。
- 浏览器请求从 `/api/chat/stream` 进入 Web 代理，再到 AI API；Agent 的实时阶段
  使用 SSE 返回。
- 查看模型模式和 Prompt 版本：`curl http://localhost:8000/health`。
- 查看请求指标：`curl http://localhost:8000/observability`。
- 调试写操作时先停在 dry-run，除非确实需要验证写入，否则不要点击确认。

## 回归测试

```bash
cd services/demo-core-api && .venv/bin/pytest
cd services/ai-api && .venv/bin/pytest
cd apps/web && npm test && npm run typecheck && npm run build
```

重新发布或推送前还应运行：

```bash
python3 scripts/security_scan.py
git diff --check
```
