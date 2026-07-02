# PostgreSQL 时间字段改为 timestamp without time zone 操作文档

## 结论

本次改造目标是：新建表时不再创建 `timestamptz`，现有库中已存在的 `timestamptz` 时间列转换为 `timestamp without time zone`。

当前实现采用两层处理：

- 新库建表：ORM 和 Alembic 建表迁移使用 `DateTime()`，PostgreSQL 下会生成 `timestamp without time zone`。
- 现有库转换：新增 Alembic 迁移 `geo_monitoring_0015`，并提供手工脚本 `backend/scripts/migrate_timestamptz_to_timestamp.sql`。

默认转换口径为上海时间：`timestamptz_col AT TIME ZONE 'Asia/Shanghai'`。转换后会把同一个绝对时间保存为北京时间墙钟值，例如 `2026-07-02 00:00:00+00` 会落成无时区的 `2026-07-02 08:00:00`。只有明确希望保存 UTC 墙钟值时，才把 `app_timezone` 覆盖为 `UTC`。

## 在线程度说明

PostgreSQL 执行 `ALTER TABLE ... ALTER COLUMN ... TYPE timestamp without time zone` 会持有 `ACCESS EXCLUSIVE` 锁，并且可能重写表数据。它不能做到完全零锁在线迁移。

当前脚本已经做了低风险处理：

- 每个字段独立执行，不把所有表字段包在一个大事务里。
- 设置 `lock_timeout`，拿不到锁会快速失败，避免长期阻塞业务。
- 设置 `statement_timeout`，避免单列转换无限执行。
- 已是目标类型的字段会自动跳过，可重复执行。

建议在业务低峰执行；大表上线前必须先在同规格备份库或预发库演练。

## 前置检查

1. 备份生产数据库和报告目录。
2. 确认当前 Alembic 版本：

```powershell
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini current
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini heads
```

3. 预检查仍为 `timestamptz` 的业务字段：

```sql
SELECT table_schema, table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name LIKE 'geo_%'
  AND udt_name = 'timestamptz'
ORDER BY table_name, ordinal_position;
```

4. 检查是否存在长事务或会阻塞 DDL 的会话：

```sql
SELECT pid, usename, state, wait_event_type, wait_event, xact_start, query
FROM pg_stat_activity
WHERE datname = current_database()
ORDER BY xact_start NULLS LAST;
```

## 推荐执行方式：Alembic

适合随版本发布执行：

```powershell
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head
```

`geo_monitoring_0015` 会扫描 `public.geo_%` 下仍为 `timestamptz` 的字段，并按列转换为 `timestamp without time zone`。

注意：`alembic upgrade head --sql` 只能用于语法预览。由于离线 SQL 模式不能扫描真实库的 `information_schema`，`geo_monitoring_0015` 在该模式下只输出提示注释，不会生成现有库的转换 SQL。现有库转换必须使用在线 Alembic 或下方手工脚本。

## 手工脚本方式

适合 DBA 单独执行或需要调整超时时间时使用。注意：`psql` 连接串需要使用 libpq 格式，例如 `postgresql://user:password@host:5432/dbname`，不要使用 SQLAlchemy 的 `postgresql+psycopg2://...`。

默认上海时间口径执行：

```powershell
psql "postgresql://<user>:<password>@<host>:5432/<db>" -v ON_ERROR_STOP=1 -f backend/scripts/migrate_timestamptz_to_timestamp.sql
```

覆盖参数示例：

```powershell
psql "postgresql://<user>:<password>@<host>:5432/<db>" `
  -v ON_ERROR_STOP=1 `
  -v app_timezone='Asia/Shanghai' `
  -v table_schema='public' `
  -v table_prefix='geo_%' `
  -v lock_timeout='5s' `
  -v statement_timeout='30min' `
  -f backend/scripts/migrate_timestamptz_to_timestamp.sql
```

如果确认业务要保存 UTC 墙钟值，将 `app_timezone` 改为 `UTC`，但必须同步确认后端对无时区时间的解释口径，避免新旧数据相差 8 小时。

## 执行后验证

1. 确认没有剩余 `timestamptz` 业务字段：

```sql
SELECT table_schema, table_name, column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name LIKE 'geo_%'
  AND udt_name = 'timestamptz'
ORDER BY table_name, ordinal_position;
```

预期返回 0 行。

2. 抽查目标字段类型：

```sql
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name LIKE 'geo_%'
  AND udt_name = 'timestamp'
ORDER BY table_name, ordinal_position;
```

3. 确认 Alembic 版本：

```powershell
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini current
```

4. 执行后端最小回归：

```powershell
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\test_timestamp_migration.py backend\tests\test_migration_baseline.py
```

## 回滚

优先使用发布前备份恢复。若需要用 Alembic 回退，可执行：

```powershell
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini downgrade geo_monitoring_0014
```

回退会按上海时间口径将 `timestamp without time zone` 转回 `timestamptz`。回退前同样需要备份，并确认没有新的后续迁移依赖 `geo_monitoring_0015`。
