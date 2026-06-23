-- GEO-Platform 报告 PDF 格式增量迁移脚本
-- 适用场景：已通过 Navicat 连接服务器 PostgreSQL，需要把现有库从 geo_monitoring_0005 升级到 geo_monitoring_0006。
-- 作用：允许 geo_report.format 写入 'pdf'，并更新 alembic_version。
-- 执行前建议：先备份数据库；确认当前库是应用正在使用的目标库。

BEGIN;

DO $$
DECLARE
    v_version TEXT;
BEGIN
    IF to_regclass('public.alembic_version') IS NULL THEN
        RAISE EXCEPTION '缺少 alembic_version 表：请确认目标库已完成 GEO-Platform 基础建表';
    END IF;

    IF to_regclass('public.geo_report') IS NULL THEN
        RAISE EXCEPTION '缺少 geo_report 表：请确认目标库已完成 geo_monitoring_0004 及后续迁移';
    END IF;

    SELECT version_num
      INTO v_version
      FROM public.alembic_version
     LIMIT 1;

    IF v_version NOT IN ('geo_monitoring_0005', 'geo_monitoring_0006') THEN
        RAISE EXCEPTION '当前 alembic_version 为 %，本脚本只支持从 geo_monitoring_0005 升级到 geo_monitoring_0006，或在 geo_monitoring_0006 上重复校正约束', v_version;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_constraint c
          JOIN pg_class t ON t.oid = c.conrelid
          JOIN pg_namespace n ON n.oid = t.relnamespace
         WHERE n.nspname = 'public'
           AND t.relname = 'geo_report'
           AND c.conname = 'ck_geo_report_format'
    ) THEN
        ALTER TABLE public.geo_report DROP CONSTRAINT ck_geo_report_format;
    END IF;

    ALTER TABLE public.geo_report
        ADD CONSTRAINT ck_geo_report_format
        CHECK (format IN ('md', 'html', 'pdf'));

    IF v_version = 'geo_monitoring_0005' THEN
        UPDATE public.alembic_version
           SET version_num = 'geo_monitoring_0006'
         WHERE version_num = 'geo_monitoring_0005';
    END IF;
END $$;

COMMIT;

-- 验收 1：版本应为 geo_monitoring_0006
SELECT version_num
  FROM public.alembic_version;

-- 验收 2：约束定义应包含 md、html、pdf
SELECT c.conname,
       pg_get_constraintdef(c.oid) AS constraint_definition
  FROM pg_constraint c
  JOIN pg_class t ON t.oid = c.conrelid
  JOIN pg_namespace n ON n.oid = t.relnamespace
 WHERE n.nspname = 'public'
   AND t.relname = 'geo_report'
   AND c.conname = 'ck_geo_report_format';
