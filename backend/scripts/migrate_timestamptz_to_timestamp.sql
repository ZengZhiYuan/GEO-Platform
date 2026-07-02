-- 将业务表中仍为 timestamptz 的时间列改为 timestamp without time zone。
--
-- 说明：
-- 1. 默认按 Asia/Shanghai 墙钟时间保存，符合当前业务要求。
-- 2. 如需保留 UTC 墙钟时间，可执行时覆盖 app_timezone：
--      psql "$DATABASE_URL" -v app_timezone='UTC' -f backend/scripts/migrate_timestamptz_to_timestamp.sql
-- 3. ALTER COLUMN TYPE 会持有 ACCESS EXCLUSIVE 锁并可能重写表；本脚本通过 lock_timeout、
--    statement_timeout 和 psql \gexec 让每一列独立执行，减少锁等待与锁累计，但不是零锁迁移。
-- 4. 已为目标类型的列会自动跳过。默认只处理 public.geo_% 业务表；如需扩大范围，
--    可覆盖 table_schema / table_prefix 变量。
--
-- 用法（psql）：
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/scripts/migrate_timestamptz_to_timestamp.sql
--
-- 预览待执行 SQL：
--   将文件最后一行的 \gexec 临时改为分号后执行，确认输出再恢复。

\set ON_ERROR_STOP on

\if :{?table_schema}
\else
\set table_schema public
\endif
\if :{?table_prefix}
\else
\set table_prefix geo_%
\endif
\if :{?app_timezone}
\else
\set app_timezone Asia/Shanghai
\endif
\if :{?lock_timeout}
\else
\set lock_timeout 5s
\endif
\if :{?statement_timeout}
\else
\set statement_timeout 30min
\endif

SET lock_timeout TO :'lock_timeout';
SET statement_timeout TO :'statement_timeout';

SELECT format(
    'ALTER TABLE %I.%I ALTER COLUMN %I TYPE timestamp WITHOUT TIME ZONE USING %I AT TIME ZONE %L;',
    table_schema,
    table_name,
    column_name,
    column_name,
    :'app_timezone'
)
FROM information_schema.columns
WHERE table_schema = :'table_schema'
  AND table_name LIKE :'table_prefix'
  AND udt_name = 'timestamptz'
ORDER BY table_name, ordinal_position
\gexec
