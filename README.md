# 实朴GEO

实朴GEO 是一个面向小红书、知乎、微信公众号等自媒体平台的内容生成 Web 应用。

## 模块

### 素材中心

- 关键词库
- 标题灵感
- 画像图库
- 品牌知识库

### 写作工作台

- 写作规范
- 内容分类
- 写作任务
- 文章清单

## 后端启动

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
````

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

## Docker启动

```bash
docker compose up -d
```

## 数据库迁移

迁移使用 Alembic，连接地址从 `app.core.config.settings.DATABASE_URL` 读取
（默认值与根目录 `.env.example` 一致，可通过 `.env` 覆盖）。
执行 `upgrade` / `--autogenerate` 需要 PostgreSQL 已启动（见 Docker 启动）。

```bash
cd backend
# 生成迁移（需连接数据库以对比表结构）
alembic revision --autogenerate -m "your message"
# 应用迁移
alembic upgrade head
# 仅生成 SQL 而不连接数据库（离线预览）
alembic upgrade head --sql
```