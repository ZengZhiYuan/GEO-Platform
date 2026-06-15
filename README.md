# AI 应用监测平台

本项目用于配置监测项目、品牌、版本化 Prompt 和 AI 平台，并创建监测运行及其查询任务。当前版本完成配置域、运行落库骨架和管理端壳层；真实平台采集、指标分析、Agent 分析、调度与报告尚未实现。

## 当前能力

- 监测项目、品牌与品牌别名管理
- Prompt 集版本管理、激活与内容摘要
- AI 平台参数管理
- 监测运行创建及 Prompt×Platform 查询任务扇出
- PostgreSQL、Redis、Dramatiq 基础设施
- React + Ant Design 监测管理端壳层

## 后端

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

接口前缀为 `/api/geo-monitoring`，健康检查为 `/api/health`。

## 前端

```powershell
cd frontend
npm ci
npm run dev
```

当前管理端入口为 `/monitoring`。

## 中间件

```powershell
docker compose up -d postgres redis
docker compose ps
```

PostgreSQL 用于业务数据，Redis 与 Dramatiq 保留给后续采集 Worker。当前版本不会投递或消费采集任务。

## 数据库迁移

当前迁移是新的监测业务基线 `geo_monitoring_0001`。不要直接应用到包含旧迁移历史的数据库；应使用空数据库或明确清理后的开发环境。

```powershell
cd backend
python -m alembic heads
python -m alembic upgrade head --sql
python -m alembic upgrade head
```

## 验证

```powershell
cd backend
python -m pytest -v

cd ../frontend
npm test
npm run build
```

平台密钥和适配器配置将在真实采集能力实现时引入。不要在仓库、日志或普通数据库字段中保存明文密钥。
