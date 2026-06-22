# PostgreSQL 建表操作文档

适用范围：GEO-Platform 后端当前 Alembic 迁移链，目标版本 `geo_monitoring_0004`。

推荐用 Alembic 在服务器上建表。它会按迁移顺序创建所有表、索引、约束，写入 `alembic_version`，并初始化 `geo_ai_platform` 默认平台数据。

## 1. 前置条件

- 服务器已安装 PostgreSQL，并能使用 `psql` 登录。
- 服务器已部署本仓库代码。
- 后端 Python 虚拟环境使用 `backend/.venv`。
- 后端依赖已安装：

```bash
cd /opt/GEO-Platform
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
```

如果 `backend/.venv` 已存在，只需确认依赖已安装：

```bash
cd /opt/GEO-Platform
backend/.venv/bin/python -m pip install -r backend/requirements.txt
```

## 2. 创建数据库和用户

以 PostgreSQL 管理员身份进入 `psql`：

```bash
sudo -u postgres psql
```

执行以下 SQL。请先替换密码。

```sql
CREATE USER geo_app WITH PASSWORD '<强密码>';
CREATE DATABASE geo_platform OWNER geo_app ENCODING 'UTF8';
GRANT ALL PRIVILEGES ON DATABASE geo_platform TO geo_app;
\q
```

验证应用用户可以连接：

```bash
psql "postgresql://geo_app:<强密码>@127.0.0.1:5432/geo_platform" -c "SELECT current_database(), current_user;"
```

如果数据库不在本机，把 `127.0.0.1` 换成 PostgreSQL 服务器地址。

## 3. 配置后端环境变量

在仓库根目录创建或修改 `.env`：

```bash
cd /opt/GEO-Platform
cp .env.example .env
vi .env
```

至少确认以下两项存在：

```dotenv
DATABASE_URL=postgresql+psycopg2://geo_app:<URL编码后的密码>@<pgsql-host>:5432/geo_platform
REDIS_URL=redis://:<redis-password>@<redis-host>:6379/0
```

注意：

- `DATABASE_URL` 必须使用 `postgresql+psycopg2://`。
- 密码里如果有 `@`、`#`、`:`、`/`、空格等特殊字符，需要做 URL 编码。
- 建表过程本身不连接 Redis，但后端配置初始化要求 `REDIS_URL` 存在。

不想写 `.env` 时，也可以在当前 shell 中临时导出：

```bash
export DATABASE_URL='postgresql+psycopg2://geo_app:<URL编码后的密码>@<pgsql-host>:5432/geo_platform'
export REDIS_URL='redis://:<redis-password>@<redis-host>:6379/0'
```

## 4. 执行建表迁移

在仓库根目录执行：

```bash
cd /opt/GEO-Platform
backend/.venv/bin/python -m alembic -c backend/alembic.ini heads
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/python -m alembic -c backend/alembic.ini current
```

预期：

- `heads` 输出包含 `geo_monitoring_0004 (head)`。
- `upgrade head` 无报错。
- `current` 输出当前版本为 `geo_monitoring_0004`。

## 5. 验收建表结果

执行：

```bash
psql "postgresql://geo_app:<强密码>@<pgsql-host>:5432/geo_platform" \
  -c "SELECT version_num FROM alembic_version;"
```

预期：

```text
geo_monitoring_0004
```

检查表数量：

```bash
psql "postgresql://geo_app:<强密码>@<pgsql-host>:5432/geo_platform" \
  -c "SELECT count(*) AS table_count FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';"
```

预期为 `19`：`18` 张业务表，加 `alembic_version`。

检查业务表：

```bash
psql "postgresql://geo_app:<强密码>@<pgsql-host>:5432/geo_platform" \
  -c "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"
```

应包含：

```text
alembic_version
geo_agent_execution
geo_ai_platform
geo_answer
geo_answer_brand_result
geo_answer_citation
geo_brand
geo_brand_alias
geo_metric_snapshot
geo_monitor_project
geo_monitor_run
geo_monitor_schedule
geo_platform_analysis
geo_prompt
geo_prompt_competitiveness
geo_prompt_set
geo_query_task
geo_report
geo_source_stat
```

检查默认平台数据：

```bash
psql "postgresql://geo_app:<强密码>@<pgsql-host>:5432/geo_platform" \
  -c "SELECT platform_code, platform_name, adapter_type FROM geo_ai_platform ORDER BY platform_code;"
```

应包含 `deepseek`、`doubao`、`kimi`、`qwen`、`yuanbao` 5 条记录。

## 6. 纯 SQL 执行方式

如果服务器不能直接连库执行 Alembic，可以先生成 SQL，再由 DBA 使用 `psql` 执行。

生成 SQL：

```bash
cd /opt/GEO-Platform
export DATABASE_URL='postgresql+psycopg2://geo_app:<URL编码后的密码>@<pgsql-host>:5432/geo_platform'
export REDIS_URL='redis://:<redis-password>@<redis-host>:6379/0'
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head --sql > /tmp/geo_platform_schema.sql
```

执行 SQL：

```bash
psql "postgresql://geo_app:<强密码>@<pgsql-host>:5432/geo_platform" -f /tmp/geo_platform_schema.sql
```

执行后仍按第 5 节验收。

## 7. 常见问题

### `Field required: DATABASE_URL`

说明当前 shell 或 `.env` 没有配置 `DATABASE_URL`。按第 3 节补齐。

### `Field required: REDIS_URL`

说明当前 shell 或 `.env` 没有配置 `REDIS_URL`。建表不使用 Redis，但配置初始化要求该值存在。

### `password authentication failed`

确认用户名、密码、主机、端口、数据库名是否正确。密码包含特殊字符时，`DATABASE_URL` 中必须使用 URL 编码后的密码。

### `permission denied for schema public`

用 PostgreSQL 管理员执行：

```sql
\c geo_platform
GRANT USAGE, CREATE ON SCHEMA public TO geo_app;
ALTER SCHEMA public OWNER TO geo_app;
```

然后重新执行：

```bash
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
```

### 已经手工建过部分表

不要直接重复执行 `upgrade head`。先备份数据库，再检查：

```bash
psql "postgresql://geo_app:<强密码>@<pgsql-host>:5432/geo_platform" \
  -c "SELECT version_num FROM alembic_version;"
```

如果没有 `alembic_version`，需要根据已有表结构决定是清库重建，还是用 `alembic stamp` 标记版本。生产库不要在未确认表结构一致时执行 `stamp`。

## 8. 回滚说明

新库建表失败且没有业务数据时，最简单的处理方式是删除数据库后重建：

```bash
sudo -u postgres psql
```

```sql
DROP DATABASE geo_platform;
CREATE DATABASE geo_platform OWNER geo_app ENCODING 'UTF8';
\q
```

然后重新从第 4 节执行迁移。

生产库或已有数据的库，不建议直接执行 `DROP DATABASE`。请先备份，并按 Alembic 版本逐步评估回滚。
