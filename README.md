# 实朴GEO启动命令

## 后端本地启动

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 前端本地启动

```bash
cd frontend
npm install
npm run dev
```

## Docker 启动

```bash
docker compose up -d
```

## 数据库迁移

```bash
cd backend
alembic revision --autogenerate -m "init"
alembic upgrade head
```

## 后端测试

```bash
cd backend
pytest
```

## 前端检查

```bash
cd frontend
npm run lint
npm run build
```