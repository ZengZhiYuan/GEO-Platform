-- AI 应用监测模块 PostgreSQL 一键建表脚本
-- 适用：PostgreSQL 14+
-- 执行方式：psql "$DATABASE_URL" -f init_geo_monitoring.sql
-- 说明：MVP 暂不建设权限、日志审计和 API Key 明文存储。

BEGIN;

CREATE TABLE IF NOT EXISTS geo_monitor_project (
    id BIGSERIAL PRIMARY KEY,
    project_name VARCHAR(100) NOT NULL,
    industry VARCHAR(100) NOT NULL DEFAULT '文旅演艺',
    description TEXT,
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    official_domain VARCHAR(255),
    report_title VARCHAR(255),
    report_subtitle VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT ck_geo_monitor_project_status CHECK (status IN ('active', 'disabled', 'archived'))
);

CREATE TABLE IF NOT EXISTS geo_brand (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES geo_monitor_project(id) ON DELETE CASCADE,
    brand_name VARCHAR(255) NOT NULL,
    brand_type VARCHAR(20) NOT NULL DEFAULT 'competitor',
    official_domain VARCHAR(255),
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_brand_project_name UNIQUE (project_id, brand_name),
    CONSTRAINT ck_geo_brand_type CHECK (brand_type IN ('target', 'competitor', 'candidate')),
    CONSTRAINT ck_geo_brand_status CHECK (status IN ('active', 'disabled'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_geo_brand_one_target_per_project
    ON geo_brand(project_id)
    WHERE brand_type = 'target' AND is_deleted = FALSE;

CREATE TABLE IF NOT EXISTS geo_brand_alias (
    id BIGSERIAL PRIMARY KEY,
    brand_id BIGINT NOT NULL REFERENCES geo_brand(id) ON DELETE CASCADE,
    alias_name VARCHAR(255) NOT NULL,
    match_mode VARCHAR(20) NOT NULL DEFAULT 'contains',
    is_ambiguous BOOLEAN NOT NULL DEFAULT FALSE,
    context_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_brand_alias UNIQUE (brand_id, alias_name),
    CONSTRAINT ck_geo_brand_alias_match_mode CHECK (match_mode IN ('exact', 'contains', 'context'))
);

CREATE TABLE IF NOT EXISTS geo_prompt_set (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES geo_monitor_project(id) ON DELETE CASCADE,
    set_name VARCHAR(100) NOT NULL,
    version_no VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    prompt_count INTEGER NOT NULL DEFAULT 0,
    checksum VARCHAR(64),
    activated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_prompt_set_version UNIQUE (project_id, version_no),
    CONSTRAINT ck_geo_prompt_set_status CHECK (status IN ('draft', 'active', 'archived'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_geo_prompt_set_one_active_per_project
    ON geo_prompt_set(project_id)
    WHERE status = 'active' AND is_deleted = FALSE;

CREATE TABLE IF NOT EXISTS geo_prompt (
    id BIGSERIAL PRIMARY KEY,
    prompt_set_id BIGINT NOT NULL REFERENCES geo_prompt_set(id) ON DELETE CASCADE,
    prompt_code VARCHAR(64) NOT NULL,
    prompt_text TEXT NOT NULL,
    prompt_type VARCHAR(50) NOT NULL DEFAULT 'generic',
    scene_tag VARCHAR(100),
    contains_brand BOOLEAN NOT NULL DEFAULT FALSE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    content_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_prompt_code UNIQUE (prompt_set_id, prompt_code)
);

CREATE TABLE IF NOT EXISTS geo_ai_platform (
    id BIGSERIAL PRIMARY KEY,
    platform_code VARCHAR(32) NOT NULL UNIQUE,
    platform_name VARCHAR(100) NOT NULL,
    adapter_type VARCHAR(50) NOT NULL DEFAULT 'openai_compatible',
    base_url VARCHAR(500),
    model_name VARCHAR(255),
    search_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    citation_supported BOOLEAN NOT NULL DEFAULT FALSE,
    max_concurrency INTEGER NOT NULL DEFAULT 2,
    timeout_seconds INTEGER NOT NULL DEFAULT 120,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    extra_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT ck_geo_ai_platform_max_concurrency CHECK (max_concurrency > 0),
    CONSTRAINT ck_geo_ai_platform_timeout CHECK (timeout_seconds > 0)
);

CREATE TABLE IF NOT EXISTS geo_monitor_schedule (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES geo_monitor_project(id) ON DELETE CASCADE,
    prompt_set_id BIGINT NOT NULL REFERENCES geo_prompt_set(id),
    schedule_name VARCHAR(100) NOT NULL,
    cron_expr VARCHAR(100) NOT NULL,
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
    platform_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    auto_generate_report BOOLEAN NOT NULL DEFAULT FALSE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    next_run_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT
);

CREATE TABLE IF NOT EXISTS geo_monitor_run (
    id BIGSERIAL PRIMARY KEY,
    run_no VARCHAR(64) NOT NULL UNIQUE,
    project_id BIGINT NOT NULL REFERENCES geo_monitor_project(id),
    prompt_set_id BIGINT NOT NULL REFERENCES geo_prompt_set(id),
    trigger_type VARCHAR(20) NOT NULL DEFAULT 'manual',
    schedule_id BIGINT REFERENCES geo_monitor_schedule(id) ON DELETE SET NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    collection_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    analysis_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    report_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    platform_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    expected_query_count INTEGER NOT NULL DEFAULT 0,
    success_query_count INTEGER NOT NULL DEFAULT 0,
    failed_query_count INTEGER NOT NULL DEFAULT 0,
    valid_answer_count INTEGER NOT NULL DEFAULT 0,
    data_completeness_rate NUMERIC(8,4) NOT NULL DEFAULT 0,
    previous_comparable_run_id BIGINT REFERENCES geo_monitor_run(id) ON DELETE SET NULL,
    result_json JSONB,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT ck_geo_monitor_run_trigger_type CHECK (trigger_type IN ('manual', 'schedule', 'retry')),
    CONSTRAINT ck_geo_monitor_run_status CHECK (status IN ('pending', 'collecting', 'analyzing', 'reporting', 'completed', 'partial_success', 'failed', 'cancelled')),
    CONSTRAINT ck_geo_monitor_run_stage_status_collection CHECK (collection_status IN ('pending', 'running', 'completed', 'partial_success', 'failed', 'cancelled')),
    CONSTRAINT ck_geo_monitor_run_stage_status_analysis CHECK (analysis_status IN ('pending', 'running', 'completed', 'partial_success', 'failed', 'skipped')),
    CONSTRAINT ck_geo_monitor_run_stage_status_report CHECK (report_status IN ('pending', 'running', 'completed', 'failed', 'skipped'))
);

CREATE TABLE IF NOT EXISTS geo_query_task (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    prompt_id BIGINT NOT NULL REFERENCES geo_prompt(id),
    platform_code VARCHAR(32) NOT NULL REFERENCES geo_ai_platform(platform_code),
    idempotency_key VARCHAR(128) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    key_slot INTEGER,
    retry_count INTEGER NOT NULL DEFAULT 0,
    request_json JSONB,
    response_http_status INTEGER,
    error_code VARCHAR(100),
    error_message TEXT,
    latency_ms INTEGER,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_query_task UNIQUE (run_id, prompt_id, platform_code),
    CONSTRAINT ck_geo_query_task_status CHECK (status IN ('pending', 'queued', 'running', 'success', 'failed', 'cancelled')),
    CONSTRAINT ck_geo_query_task_retry_count CHECK (retry_count >= 0)
);

CREATE TABLE IF NOT EXISTS geo_answer (
    id BIGSERIAL PRIMARY KEY,
    query_task_id BIGINT NOT NULL UNIQUE REFERENCES geo_query_task(id) ON DELETE CASCADE,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    prompt_id BIGINT NOT NULL REFERENCES geo_prompt(id),
    platform_code VARCHAR(32) NOT NULL REFERENCES geo_ai_platform(platform_code),
    model_name VARCHAR(255),
    answer_text TEXT NOT NULL,
    answer_markdown TEXT,
    answer_html TEXT,
    raw_response JSONB,
    finish_reason VARCHAR(100),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    answer_hash VARCHAR(64),
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT
);

CREATE TABLE IF NOT EXISTS geo_answer_citation (
    id BIGSERIAL PRIMARY KEY,
    answer_id BIGINT NOT NULL REFERENCES geo_answer(id) ON DELETE CASCADE,
    citation_rank INTEGER NOT NULL,
    title TEXT,
    url TEXT,
    canonical_url TEXT,
    domain VARCHAR(255),
    source_name VARCHAR(255),
    snippet TEXT,
    published_at TIMESTAMPTZ,
    is_brand_related BOOLEAN,
    brand_related_confidence NUMERIC(6,4),
    source_type VARCHAR(50),
    raw_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_answer_citation_rank UNIQUE (answer_id, citation_rank)
);

CREATE TABLE IF NOT EXISTS geo_answer_brand_result (
    id BIGSERIAL PRIMARY KEY,
    answer_id BIGINT NOT NULL REFERENCES geo_answer(id) ON DELETE CASCADE,
    brand_id BIGINT NOT NULL REFERENCES geo_brand(id),
    raw_mention VARCHAR(500),
    mentioned BOOLEAN NOT NULL DEFAULT FALSE,
    mention_count INTEGER NOT NULL DEFAULT 0,
    first_position INTEGER,
    recommendation_rank INTEGER,
    is_first_recommendation BOOLEAN,
    evidence_text TEXT,
    confidence NUMERIC(6,4),
    detection_method VARCHAR(30) NOT NULL DEFAULT 'rule',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_answer_brand_result UNIQUE (answer_id, brand_id),
    CONSTRAINT ck_geo_answer_brand_result_method CHECK (detection_method IN ('rule', 'llm', 'hybrid', 'manual'))
);

CREATE TABLE IF NOT EXISTS geo_agent_execution (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    platform_code VARCHAR(32),
    agent_code VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    schema_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    input_snapshot JSONB,
    output_json JSONB,
    model_provider VARCHAR(100),
    model_name VARCHAR(255),
    prompt_version VARCHAR(50),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT ck_geo_agent_execution_status CHECK (status IN ('pending', 'running', 'success', 'failed', 'skipped'))
);

CREATE TABLE IF NOT EXISTS geo_platform_analysis (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    platform_code VARCHAR(32) NOT NULL REFERENCES geo_ai_platform(platform_code),
    valid_answer_count INTEGER NOT NULL DEFAULT 0,
    data_completeness_rate NUMERIC(8,4) NOT NULL DEFAULT 0,
    brand_mention_count INTEGER NOT NULL DEFAULT 0,
    brand_mention_rate NUMERIC(8,4) NOT NULL DEFAULT 0,
    brand_first_count INTEGER NOT NULL DEFAULT 0,
    brand_first_rate NUMERIC(8,4) NOT NULL DEFAULT 0,
    brand_first_among_mentions_rate NUMERIC(8,4) NOT NULL DEFAULT 0,
    top_competitors JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    prompt_competitiveness_summary JSONB NOT NULL DEFAULT '[]'::jsonb,
    improvement_json JSONB,
    summary_json JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_platform_analysis UNIQUE (run_id, platform_code),
    CONSTRAINT ck_geo_platform_analysis_status CHECK (status IN ('pending', 'running', 'completed', 'partial_success', 'failed'))
);

CREATE TABLE IF NOT EXISTS geo_metric_snapshot (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES geo_monitor_project(id) ON DELETE CASCADE,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    platform_code VARCHAR(32),
    prompt_id BIGINT REFERENCES geo_prompt(id) ON DELETE SET NULL,
    metric_code VARCHAR(100) NOT NULL,
    numerator NUMERIC(18,4),
    denominator NUMERIC(18,4),
    metric_value NUMERIC(18,6),
    metric_json JSONB,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    prompt_set_version VARCHAR(50) NOT NULL,
    is_comparable BOOLEAN NOT NULL DEFAULT TRUE,
    completeness_rate NUMERIC(8,4) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT
);

CREATE TABLE IF NOT EXISTS geo_prompt_competitiveness (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    prompt_id BIGINT NOT NULL REFERENCES geo_prompt(id),
    platform_code VARCHAR(32) NOT NULL REFERENCES geo_ai_platform(platform_code),
    target_mentioned BOOLEAN NOT NULL DEFAULT FALSE,
    target_rank INTEGER,
    target_first BOOLEAN,
    competitors_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    position_label VARCHAR(30),
    competitiveness_score NUMERIC(8,4),
    evidence_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_prompt_competitiveness UNIQUE (run_id, prompt_id, platform_code)
);

CREATE TABLE IF NOT EXISTS geo_source_stat (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    platform_code VARCHAR(32),
    domain VARCHAR(255) NOT NULL,
    source_name VARCHAR(255),
    source_type VARCHAR(50),
    citation_count INTEGER NOT NULL DEFAULT 0,
    brand_related_count INTEGER NOT NULL DEFAULT 0,
    share_rate NUMERIC(8,4) NOT NULL DEFAULT 0,
    rank_no INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT
);

CREATE TABLE IF NOT EXISTS geo_report (
    id BIGSERIAL PRIMARY KEY,
    report_no VARCHAR(64) NOT NULL UNIQUE,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    report_name VARCHAR(255) NOT NULL,
    template_version VARCHAR(50) NOT NULL DEFAULT '1.0',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    html_path TEXT,
    pdf_path TEXT,
    file_size BIGINT,
    summary_json JSONB,
    error_message TEXT,
    generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT ck_geo_report_status CHECK (status IN ('pending', 'generating', 'completed', 'failed'))
);

-- 关键查询索引
CREATE INDEX IF NOT EXISTS idx_geo_brand_project_type ON geo_brand(project_id, brand_type) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_brand_alias_name ON geo_brand_alias(alias_name) WHERE enabled = TRUE AND is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_prompt_set_project_status ON geo_prompt_set(project_id, status) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_prompt_prompt_set_enabled ON geo_prompt(prompt_set_id, enabled, sort_order) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_schedule_project_enabled ON geo_monitor_schedule(project_id, enabled) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_run_project_created ON geo_monitor_run(project_id, created_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_run_status ON geo_monitor_run(status, created_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_query_task_run_status ON geo_query_task(run_id, status) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_query_task_platform_status ON geo_query_task(platform_code, status) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_answer_run_platform ON geo_answer(run_id, platform_code) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_answer_prompt_platform ON geo_answer(prompt_id, platform_code, collected_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_citation_domain ON geo_answer_citation(domain) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_brand_result_brand_mentioned ON geo_answer_brand_result(brand_id, mentioned) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_agent_run_platform ON geo_agent_execution(run_id, platform_code, agent_code) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_metric_trend ON geo_metric_snapshot(project_id, metric_code, platform_code, snapshot_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_prompt_comp_run_prompt ON geo_prompt_competitiveness(run_id, prompt_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_source_stat_run_rank ON geo_source_stat(run_id, platform_code, rank_no) WHERE is_deleted = FALSE;

-- 平台基础数据。base_url/model_name 可由环境变量或管理接口覆盖。
INSERT INTO geo_ai_platform (
    platform_code, platform_name, adapter_type, search_enabled,
    citation_supported, max_concurrency, timeout_seconds, enabled
) VALUES
    ('doubao', '豆包', 'openai_compatible', FALSE, FALSE, 2, 120, TRUE),
    ('qwen', '通义千问', 'openai_compatible', FALSE, FALSE, 2, 120, TRUE),
    ('yuanbao', '腾讯元宝', 'tencent', FALSE, FALSE, 2, 120, TRUE),
    ('deepseek', 'DeepSeek', 'openai_compatible', FALSE, FALSE, 2, 120, TRUE),
    ('kimi', 'Kimi', 'openai_compatible', FALSE, FALSE, 2, 120, TRUE)
ON CONFLICT (platform_code) DO UPDATE SET
    platform_name = EXCLUDED.platform_name,
    adapter_type = EXCLUDED.adapter_type,
    search_enabled = EXCLUDED.search_enabled,
    citation_supported = EXCLUDED.citation_supported,
    updated_at = NOW();

COMMIT;
