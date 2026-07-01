BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> geo_monitoring_0001

CREATE TABLE geo_monitor_project (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    project_name VARCHAR(100) NOT NULL, 
    industry VARCHAR(100) DEFAULT '文旅演艺' NOT NULL, 
    description TEXT, 
    timezone VARCHAR(64) DEFAULT 'Asia/Shanghai' NOT NULL, 
    status VARCHAR(20) DEFAULT 'active' NOT NULL, 
    official_domain VARCHAR(255), 
    report_title VARCHAR(255), 
    report_subtitle VARCHAR(500), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_geo_monitor_project_status CHECK (status IN ('active', 'disabled', 'archived'))
);

CREATE INDEX ix_geo_monitor_project_status ON geo_monitor_project (status);

CREATE TABLE geo_brand (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    project_id BIGINT NOT NULL, 
    brand_name VARCHAR(255) NOT NULL, 
    brand_type VARCHAR(20) DEFAULT 'competitor' NOT NULL, 
    official_domain VARCHAR(255), 
    description TEXT, 
    status VARCHAR(20) DEFAULT 'active' NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_geo_brand_type CHECK (brand_type IN ('target', 'competitor', 'candidate')), 
    CONSTRAINT ck_geo_brand_status CHECK (status IN ('active', 'disabled')), 
    CONSTRAINT uq_geo_brand_project_name UNIQUE (project_id, brand_name), 
    FOREIGN KEY(project_id) REFERENCES geo_monitor_project (id) ON DELETE CASCADE
);

CREATE INDEX ix_geo_brand_project_type ON geo_brand (project_id, brand_type);

CREATE UNIQUE INDEX uq_geo_brand_one_target_per_project ON geo_brand (project_id) WHERE brand_type = 'target' AND is_deleted = false;

CREATE TABLE geo_brand_alias (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    brand_id BIGINT NOT NULL, 
    alias_name VARCHAR(255) NOT NULL, 
    match_mode VARCHAR(20) DEFAULT 'contains' NOT NULL, 
    is_ambiguous BOOLEAN DEFAULT false NOT NULL, 
    context_keywords JSONB DEFAULT '[]'::jsonb NOT NULL, 
    enabled BOOLEAN DEFAULT true NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_geo_brand_alias_match_mode CHECK (match_mode IN ('exact', 'contains', 'context')), 
    CONSTRAINT uq_geo_brand_alias UNIQUE (brand_id, alias_name), 
    FOREIGN KEY(brand_id) REFERENCES geo_brand (id) ON DELETE CASCADE
);

CREATE INDEX ix_geo_brand_alias_brand_id ON geo_brand_alias (brand_id);

CREATE INDEX ix_geo_brand_alias_name ON geo_brand_alias (alias_name);

CREATE TABLE geo_prompt_set (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    project_id BIGINT NOT NULL, 
    set_name VARCHAR(100) NOT NULL, 
    version_no VARCHAR(50) NOT NULL, 
    status VARCHAR(20) DEFAULT 'draft' NOT NULL, 
    prompt_count INTEGER DEFAULT '0' NOT NULL, 
    checksum VARCHAR(64), 
    activated_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_geo_prompt_set_status CHECK (status IN ('draft', 'active', 'archived')), 
    CONSTRAINT uq_geo_prompt_set_version UNIQUE (project_id, version_no), 
    FOREIGN KEY(project_id) REFERENCES geo_monitor_project (id) ON DELETE CASCADE
);

CREATE INDEX ix_geo_prompt_set_project_status ON geo_prompt_set (project_id, status);

CREATE UNIQUE INDEX uq_geo_prompt_set_one_active_per_project ON geo_prompt_set (project_id) WHERE status = 'active' AND is_deleted = false;

CREATE TABLE geo_prompt (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    prompt_set_id BIGINT NOT NULL, 
    prompt_code VARCHAR(64) NOT NULL, 
    prompt_text TEXT NOT NULL, 
    prompt_type VARCHAR(50) DEFAULT 'generic' NOT NULL, 
    scene_tag VARCHAR(100), 
    contains_brand BOOLEAN DEFAULT false NOT NULL, 
    enabled BOOLEAN DEFAULT true NOT NULL, 
    sort_order INTEGER DEFAULT '0' NOT NULL, 
    content_hash VARCHAR(64), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_geo_prompt_code UNIQUE (prompt_set_id, prompt_code), 
    FOREIGN KEY(prompt_set_id) REFERENCES geo_prompt_set (id) ON DELETE CASCADE
);

CREATE INDEX ix_geo_prompt_prompt_set_enabled ON geo_prompt (prompt_set_id, enabled, sort_order);

CREATE TABLE geo_ai_platform (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    platform_code VARCHAR(32) NOT NULL, 
    platform_name VARCHAR(100) NOT NULL, 
    adapter_type VARCHAR(50) DEFAULT 'openai_compatible' NOT NULL, 
    base_url VARCHAR(500), 
    model_name VARCHAR(255), 
    search_enabled BOOLEAN DEFAULT true NOT NULL, 
    citation_supported BOOLEAN DEFAULT false NOT NULL, 
    max_concurrency INTEGER DEFAULT '2' NOT NULL, 
    timeout_seconds INTEGER DEFAULT '120' NOT NULL, 
    enabled BOOLEAN DEFAULT true NOT NULL, 
    extra_config JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_geo_ai_platform_max_concurrency CHECK (max_concurrency > 0), 
    CONSTRAINT ck_geo_ai_platform_timeout CHECK (timeout_seconds > 0), 
    CONSTRAINT uq_geo_ai_platform_code UNIQUE (platform_code)
);

CREATE UNIQUE INDEX ix_geo_ai_platform_platform_code ON geo_ai_platform (platform_code);

CREATE TABLE geo_monitor_run (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    run_no VARCHAR(64) NOT NULL, 
    project_id BIGINT NOT NULL, 
    prompt_set_id BIGINT NOT NULL, 
    prompt_set_version VARCHAR(50) NOT NULL, 
    trigger_type VARCHAR(20) DEFAULT 'manual' NOT NULL, 
    status VARCHAR(30) DEFAULT 'pending' NOT NULL, 
    collection_status VARCHAR(30) DEFAULT 'pending' NOT NULL, 
    analysis_status VARCHAR(30) DEFAULT 'skipped' NOT NULL, 
    report_status VARCHAR(30) DEFAULT 'skipped' NOT NULL, 
    platform_codes JSONB DEFAULT '[]'::jsonb NOT NULL, 
    expected_query_count INTEGER DEFAULT '0' NOT NULL, 
    success_query_count INTEGER DEFAULT '0' NOT NULL, 
    failed_query_count INTEGER DEFAULT '0' NOT NULL, 
    valid_answer_count INTEGER DEFAULT '0' NOT NULL, 
    data_completeness_rate NUMERIC(8, 4) DEFAULT '0' NOT NULL, 
    result_json JSONB, 
    error_message TEXT, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_geo_monitor_run_trigger_type CHECK (trigger_type IN ('manual', 'schedule', 'retry')), 
    CONSTRAINT ck_geo_monitor_run_status CHECK (status IN ('pending', 'collecting', 'analyzing', 'reporting', 'completed', 'partial_success', 'failed', 'cancelled')), 
    CONSTRAINT ck_geo_monitor_run_collection_status CHECK (collection_status IN ('pending', 'running', 'completed', 'partial_success', 'failed', 'cancelled')), 
    CONSTRAINT ck_geo_monitor_run_analysis_status CHECK (analysis_status IN ('pending', 'running', 'completed', 'partial_success', 'failed', 'skipped')), 
    CONSTRAINT ck_geo_monitor_run_report_status CHECK (report_status IN ('pending', 'running', 'completed', 'failed', 'skipped')), 
    CONSTRAINT uq_geo_monitor_run_no UNIQUE (run_no), 
    FOREIGN KEY(project_id) REFERENCES geo_monitor_project (id), 
    FOREIGN KEY(prompt_set_id) REFERENCES geo_prompt_set (id)
);

CREATE INDEX ix_geo_monitor_run_project_created ON geo_monitor_run (project_id, created_at);

CREATE INDEX ix_geo_monitor_run_status ON geo_monitor_run (status, created_at);

CREATE TABLE geo_query_task (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    run_id BIGINT NOT NULL, 
    prompt_id BIGINT NOT NULL, 
    platform_code VARCHAR(32) NOT NULL, 
    idempotency_key VARCHAR(128) NOT NULL, 
    status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
    key_slot INTEGER, 
    retry_count INTEGER DEFAULT '0' NOT NULL, 
    request_json JSONB, 
    response_http_status INTEGER, 
    error_code VARCHAR(100), 
    error_message TEXT, 
    latency_ms INTEGER, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_geo_query_task_status CHECK (status IN ('pending', 'queued', 'running', 'success', 'failed', 'cancelled')), 
    CONSTRAINT ck_geo_query_task_retry_count CHECK (retry_count >= 0), 
    CONSTRAINT uq_geo_query_task UNIQUE (run_id, prompt_id, platform_code), 
    CONSTRAINT uq_geo_query_task_idempotency_key UNIQUE (idempotency_key), 
    FOREIGN KEY(run_id) REFERENCES geo_monitor_run (id) ON DELETE CASCADE, 
    FOREIGN KEY(prompt_id) REFERENCES geo_prompt (id), 
    FOREIGN KEY(platform_code) REFERENCES geo_ai_platform (platform_code)
);

CREATE INDEX ix_geo_query_task_run_status ON geo_query_task (run_id, status);

CREATE INDEX ix_geo_query_task_platform_status ON geo_query_task (platform_code, status);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type) VALUES ('doubao', '豆包', 'openai_compatible');

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type) VALUES ('qwen', '通义千问', 'openai_compatible');

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type) VALUES ('yuanbao', '腾讯元宝', 'tencent');

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type) VALUES ('deepseek', 'DeepSeek', 'openai_compatible');

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type) VALUES ('kimi', 'Kimi', 'openai_compatible');

INSERT INTO alembic_version (version_num) VALUES ('geo_monitoring_0001') RETURNING alembic_version.version_num;

-- Running upgrade geo_monitoring_0001 -> geo_monitoring_0002

ALTER TABLE geo_monitor_run ADD COLUMN triggered_by BIGINT;

ALTER TABLE geo_monitor_run ADD COLUMN total_tasks INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE geo_monitor_run ADD COLUMN succeeded_tasks INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE geo_monitor_run ADD COLUMN failed_tasks INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE geo_monitor_run ADD COLUMN cancelled_tasks INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE geo_monitor_run ADD COLUMN completed_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE geo_monitor_run ADD COLUMN error_summary TEXT;

CREATE INDEX ix_geo_monitor_run_status_completed ON geo_monitor_run (status, completed_at);

ALTER TABLE geo_query_task ADD COLUMN attempt_count INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE geo_query_task ADD COLUMN max_attempts INTEGER DEFAULT '3' NOT NULL;

ALTER TABLE geo_query_task ADD COLUMN queued_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE geo_query_task ADD COLUMN completed_at TIMESTAMP WITH TIME ZONE;

ALTER TABLE geo_query_task ADD COLUMN last_error_code VARCHAR(100);

ALTER TABLE geo_query_task ADD COLUMN last_error_message TEXT;

ALTER TABLE geo_query_task ADD COLUMN provider_request_id VARCHAR(255);

CREATE INDEX ix_geo_query_task_status_queued ON geo_query_task (status, queued_at);

CREATE TABLE geo_answer (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    task_id BIGINT NOT NULL, 
    platform_code VARCHAR(32) NOT NULL, 
    prompt_id BIGINT NOT NULL, 
    raw_text TEXT NOT NULL, 
    normalized_text TEXT, 
    model_name VARCHAR(255), 
    prompt_tokens INTEGER DEFAULT '0' NOT NULL, 
    completion_tokens INTEGER DEFAULT '0' NOT NULL, 
    total_tokens INTEGER DEFAULT '0' NOT NULL, 
    latency_ms INTEGER, 
    collected_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    raw_response_json JSONB, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_geo_answer_task UNIQUE (task_id), 
    FOREIGN KEY(task_id) REFERENCES geo_query_task (id) ON DELETE CASCADE, 
    FOREIGN KEY(platform_code) REFERENCES geo_ai_platform (platform_code), 
    FOREIGN KEY(prompt_id) REFERENCES geo_prompt (id)
);

CREATE INDEX ix_geo_answer_platform_collected ON geo_answer (platform_code, collected_at);

CREATE TABLE geo_answer_citation (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    answer_id BIGINT NOT NULL, 
    citation_no INTEGER NOT NULL, 
    title VARCHAR(500), 
    url TEXT, 
    domain VARCHAR(255), 
    source_type VARCHAR(50), 
    quoted_text TEXT, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_geo_answer_citation_answer_no UNIQUE (answer_id, citation_no), 
    FOREIGN KEY(answer_id) REFERENCES geo_answer (id) ON DELETE CASCADE
);

CREATE INDEX ix_geo_answer_citation_domain ON geo_answer_citation (domain);

CREATE TABLE geo_answer_brand_result (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    answer_id BIGINT NOT NULL, 
    brand_id BIGINT NOT NULL, 
    is_mentioned BOOLEAN DEFAULT false NOT NULL, 
    mention_count INTEGER DEFAULT '0' NOT NULL, 
    first_position INTEGER, 
    sentiment VARCHAR(30), 
    context_json JSONB DEFAULT '{}'::jsonb NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_geo_answer_brand_result_answer_brand UNIQUE (answer_id, brand_id), 
    FOREIGN KEY(answer_id) REFERENCES geo_answer (id) ON DELETE CASCADE, 
    FOREIGN KEY(brand_id) REFERENCES geo_brand (id) ON DELETE CASCADE
);

CREATE INDEX ix_geo_answer_brand_result_brand_mentioned ON geo_answer_brand_result (brand_id, is_mentioned);

UPDATE alembic_version SET version_num='geo_monitoring_0002' WHERE alembic_version.version_num = 'geo_monitoring_0001';

-- Running upgrade geo_monitoring_0002 -> geo_monitoring_0003

CREATE TABLE geo_agent_execution (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    run_id BIGINT NOT NULL, 
    platform_code VARCHAR(32), 
    agent_code VARCHAR(64) NOT NULL, 
    status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
    schema_version VARCHAR(20) DEFAULT '1.0' NOT NULL, 
    input_snapshot JSONB, 
    output_json JSONB, 
    model_provider VARCHAR(100), 
    model_name VARCHAR(255), 
    prompt_version VARCHAR(50), 
    prompt_tokens INTEGER, 
    completion_tokens INTEGER, 
    error_message TEXT, 
    started_at TIMESTAMP WITH TIME ZONE, 
    finished_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_geo_agent_execution_status CHECK (status IN ('pending', 'running', 'success', 'failed', 'skipped')), 
    FOREIGN KEY(run_id) REFERENCES geo_monitor_run (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX uq_geo_agent_execution_run_agent ON geo_agent_execution (run_id, agent_code, schema_version, coalesce(platform_code, ''));

CREATE INDEX ix_geo_agent_execution_run_platform_agent ON geo_agent_execution (run_id, platform_code, agent_code);

CREATE TABLE geo_platform_analysis (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    run_id BIGINT NOT NULL, 
    platform_code VARCHAR(32) NOT NULL, 
    valid_answer_count INTEGER DEFAULT '0' NOT NULL, 
    data_completeness_rate NUMERIC(8, 4) DEFAULT '0' NOT NULL, 
    brand_mention_count INTEGER DEFAULT '0' NOT NULL, 
    brand_mention_rate NUMERIC(8, 4) DEFAULT '0' NOT NULL, 
    brand_first_count INTEGER DEFAULT '0' NOT NULL, 
    brand_first_rate NUMERIC(8, 4) DEFAULT '0' NOT NULL, 
    brand_first_among_mentions_rate NUMERIC(8, 4) DEFAULT '0' NOT NULL, 
    top_competitors JSONB DEFAULT '[]'::jsonb NOT NULL, 
    top_sources JSONB DEFAULT '[]'::jsonb NOT NULL, 
    prompt_competitiveness_summary JSONB DEFAULT '[]'::jsonb NOT NULL, 
    improvement_json JSONB, 
    summary_json JSONB, 
    status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_geo_platform_analysis_status CHECK (status IN ('pending', 'running', 'completed', 'partial_success', 'failed')), 
    CONSTRAINT uq_geo_platform_analysis UNIQUE (run_id, platform_code), 
    FOREIGN KEY(run_id) REFERENCES geo_monitor_run (id) ON DELETE CASCADE, 
    FOREIGN KEY(platform_code) REFERENCES geo_ai_platform (platform_code)
);

CREATE TABLE geo_metric_snapshot (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    project_id BIGINT NOT NULL, 
    run_id BIGINT NOT NULL, 
    platform_code VARCHAR(32), 
    prompt_id BIGINT, 
    metric_code VARCHAR(100) NOT NULL, 
    numerator NUMERIC(18, 4), 
    denominator NUMERIC(18, 4), 
    metric_value NUMERIC(18, 6), 
    metric_json JSONB, 
    snapshot_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    prompt_set_version VARCHAR(50) NOT NULL, 
    is_comparable BOOLEAN DEFAULT true NOT NULL, 
    completeness_rate NUMERIC(8, 4) DEFAULT '0' NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(project_id) REFERENCES geo_monitor_project (id) ON DELETE CASCADE, 
    FOREIGN KEY(run_id) REFERENCES geo_monitor_run (id) ON DELETE CASCADE, 
    FOREIGN KEY(prompt_id) REFERENCES geo_prompt (id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX uq_geo_metric_snapshot_dimension ON geo_metric_snapshot (project_id, run_id, metric_code, coalesce(platform_code, ''), coalesce(prompt_id, -1));

CREATE INDEX ix_geo_metric_snapshot_trend ON geo_metric_snapshot (project_id, metric_code, platform_code, snapshot_at);

CREATE TABLE geo_prompt_competitiveness (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    run_id BIGINT NOT NULL, 
    prompt_id BIGINT NOT NULL, 
    platform_code VARCHAR(32) NOT NULL, 
    target_mentioned BOOLEAN DEFAULT false NOT NULL, 
    target_rank INTEGER, 
    target_first BOOLEAN, 
    competitors_json JSONB DEFAULT '[]'::jsonb NOT NULL, 
    position_label VARCHAR(30), 
    competitiveness_score NUMERIC(8, 4), 
    evidence_json JSONB, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_geo_prompt_competitiveness UNIQUE (run_id, prompt_id, platform_code), 
    FOREIGN KEY(run_id) REFERENCES geo_monitor_run (id) ON DELETE CASCADE, 
    FOREIGN KEY(prompt_id) REFERENCES geo_prompt (id), 
    FOREIGN KEY(platform_code) REFERENCES geo_ai_platform (platform_code)
);

CREATE INDEX ix_geo_prompt_competitiveness_run_prompt ON geo_prompt_competitiveness (run_id, prompt_id);

CREATE TABLE geo_source_stat (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    run_id BIGINT NOT NULL, 
    platform_code VARCHAR(32), 
    domain VARCHAR(255) NOT NULL, 
    source_name VARCHAR(255), 
    source_type VARCHAR(50), 
    citation_count INTEGER DEFAULT '0' NOT NULL, 
    brand_related_count INTEGER DEFAULT '0' NOT NULL, 
    share_rate NUMERIC(8, 4) DEFAULT '0' NOT NULL, 
    rank_no INTEGER, 
    PRIMARY KEY (id), 
    FOREIGN KEY(run_id) REFERENCES geo_monitor_run (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX uq_geo_source_stat_run_platform_domain ON geo_source_stat (run_id, domain, coalesce(platform_code, ''));

CREATE INDEX ix_geo_source_stat_run_platform_rank ON geo_source_stat (run_id, platform_code, rank_no);

UPDATE alembic_version SET version_num='geo_monitoring_0003' WHERE alembic_version.version_num = 'geo_monitoring_0002';

-- Running upgrade geo_monitoring_0003 -> geo_monitoring_0004

CREATE TABLE geo_monitor_schedule (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    project_id BIGINT NOT NULL, 
    name VARCHAR(100) NOT NULL, 
    cron_expr VARCHAR(100) NOT NULL, 
    timezone VARCHAR(64) DEFAULT 'Asia/Shanghai' NOT NULL, 
    enabled BOOLEAN DEFAULT true NOT NULL, 
    next_run_at TIMESTAMP WITH TIME ZONE, 
    last_run_at TIMESTAMP WITH TIME ZONE, 
    misfire_policy VARCHAR(20) DEFAULT 'fire_once' NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_geo_monitor_schedule_misfire_policy CHECK (misfire_policy IN ('fire_once', 'ignore')), 
    FOREIGN KEY(project_id) REFERENCES geo_monitor_project (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX uq_geo_monitor_schedule_project_name ON geo_monitor_schedule (project_id, name);

CREATE INDEX ix_geo_monitor_schedule_project_enabled ON geo_monitor_schedule (project_id, enabled);

CREATE TABLE geo_report (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    project_id BIGINT NOT NULL, 
    run_id BIGINT NOT NULL, 
    status VARCHAR(20) DEFAULT 'pending' NOT NULL, 
    format VARCHAR(20) NOT NULL, 
    file_name VARCHAR(255) NOT NULL, 
    relative_storage_path VARCHAR(500) NOT NULL, 
    file_size BIGINT, 
    checksum VARCHAR(128), 
    error_message TEXT, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_geo_report_status CHECK (status IN ('pending', 'generating', 'completed', 'failed')), 
    CONSTRAINT ck_geo_report_format CHECK (format IN ('md', 'html')), 
    CONSTRAINT ck_geo_report_relative_storage_path CHECK (relative_storage_path NOT LIKE '/%' AND relative_storage_path !~ '^[A-Za-z]:' AND relative_storage_path NOT LIKE '\\%'), 
    FOREIGN KEY(project_id) REFERENCES geo_monitor_project (id) ON DELETE CASCADE, 
    FOREIGN KEY(run_id) REFERENCES geo_monitor_run (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX uq_geo_report_relative_storage_path ON geo_report (relative_storage_path);

CREATE INDEX ix_geo_report_project_run ON geo_report (project_id, run_id);

UPDATE alembic_version SET version_num='geo_monitoring_0004' WHERE alembic_version.version_num = 'geo_monitoring_0003';

-- Running upgrade geo_monitoring_0004 -> geo_monitoring_0005

ALTER TABLE geo_monitor_project ADD COLUMN default_platform_codes JSON DEFAULT '[]' NOT NULL;

CREATE TABLE geo_core_keyword (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    project_id BIGINT NOT NULL, 
    keyword VARCHAR(100) NOT NULL, 
    description TEXT, 
    sort_order INTEGER DEFAULT '0' NOT NULL, 
    enabled BOOLEAN DEFAULT true NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_geo_core_keyword_project_keyword UNIQUE (project_id, keyword), 
    FOREIGN KEY(project_id) REFERENCES geo_monitor_project (id) ON DELETE CASCADE
);

CREATE INDEX ix_geo_core_keyword_project_sort ON geo_core_keyword (project_id, sort_order);

CREATE TABLE geo_prompt_library (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITH TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    prompt_code VARCHAR(64) NOT NULL, 
    prompt_text TEXT NOT NULL, 
    prompt_type VARCHAR(50) DEFAULT 'generic' NOT NULL, 
    industry VARCHAR(100), 
    scene_tag VARCHAR(100), 
    default_core_keyword VARCHAR(100), 
    enabled BOOLEAN DEFAULT true NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_geo_prompt_library_code UNIQUE (prompt_code)
);

CREATE INDEX ix_geo_prompt_library_industry_enabled ON geo_prompt_library (industry, enabled);

ALTER TABLE geo_prompt ADD COLUMN core_keyword_id BIGINT;

ALTER TABLE geo_prompt ADD CONSTRAINT fk_geo_prompt_core_keyword_id FOREIGN KEY(core_keyword_id) REFERENCES geo_core_keyword (id) ON DELETE SET NULL;

INSERT INTO geo_prompt_library (prompt_code, prompt_text, prompt_type, industry, scene_tag, default_core_keyword, enabled, is_deleted) VALUES ('LIB_RECOMMEND_001', '推荐国内有哪些值得看的文旅演艺项目？', 'recommendation', '文旅演艺', '推荐', '文旅演艺', true, false);

INSERT INTO geo_prompt_library (prompt_code, prompt_text, prompt_type, industry, scene_tag, default_core_keyword, enabled, is_deleted) VALUES ('LIB_COMPARE_001', '宋城演艺和只有河南·戏剧幻城哪个更值得看？', 'comparison', '文旅演艺', '对比', '文旅演艺', true, false);

INSERT INTO geo_prompt_library (prompt_code, prompt_text, prompt_type, industry, scene_tag, default_core_keyword, enabled, is_deleted) VALUES ('LIB_VISIBILITY_001', '介绍一下只有河南·戏剧幻城这个品牌。', 'brand_visibility', '文旅演艺', '品牌认知', '只有河南', true, false);

UPDATE alembic_version SET version_num='geo_monitoring_0005' WHERE alembic_version.version_num = 'geo_monitoring_0004';

-- Running upgrade geo_monitoring_0005 -> geo_monitoring_0006

ALTER TABLE geo_report DROP CONSTRAINT ck_geo_report_format;

ALTER TABLE geo_report ADD CONSTRAINT ck_geo_report_format CHECK (format IN ('md', 'html', 'pdf'));

UPDATE alembic_version SET version_num='geo_monitoring_0006' WHERE alembic_version.version_num = 'geo_monitoring_0005';

-- Running upgrade geo_monitoring_0006 -> geo_monitoring_0007

ALTER TABLE geo_monitor_run ADD COLUMN collection_source VARCHAR(20) DEFAULT 'official' NOT NULL;

ALTER TABLE geo_monitor_run ADD COLUMN aidso_thinking_enabled_by_platform JSON DEFAULT '{}' NOT NULL;

ALTER TABLE geo_monitor_run ADD CONSTRAINT ck_geo_monitor_run_collection_source CHECK (collection_source IN ('official', 'aidso'));

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('aidso_doubao_web', '豆包 Web 端', 'aidso', NULL, 'aidso:DB', true, true, 2, 120, true, '{"aidso_name": "DB"}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('aidso_doubao_app', '豆包 App 端', 'aidso', NULL, 'aidso:DOUBA', true, true, 2, 120, true, '{"aidso_name": "DOUBA"}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('aidso_deepseek_web', 'DeepSeek Web 端', 'aidso', NULL, 'aidso:DP', true, true, 2, 120, true, '{"aidso_name": "DP"}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('aidso_deepseek_app', 'DeepSeek App 端', 'aidso', NULL, 'aidso:DPA', true, true, 2, 120, true, '{"aidso_name": "DPA"}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('aidso_kimi_web', 'Kimi Web 端', 'aidso', NULL, 'aidso:KIMI', true, true, 2, 120, true, '{"aidso_name": "KIMI"}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('aidso_yuanbao_web', '元宝 Web 端', 'aidso', NULL, 'aidso:TXYB', true, true, 2, 120, true, '{"aidso_name": "TXYB"}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('aidso_yuanbao_app', '元宝 App 端', 'aidso', NULL, 'aidso:TXYBA', true, true, 2, 120, true, '{"aidso_name": "TXYBA"}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('aidso_qwen_web', '千问 Web 端', 'aidso', NULL, 'aidso:TYQW', true, true, 2, 120, true, '{"aidso_name": "TYQW"}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('aidso_qwen_app', '千问 App 端', 'aidso', NULL, 'aidso:TYQWA', true, true, 2, 120, true, '{"aidso_name": "TYQWA"}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('aidso_baidu_web', '百度 AI', 'aidso', NULL, 'aidso:BDAI', true, true, 2, 120, true, '{"aidso_name": "BDAI"}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('aidso_douyin_web', '抖音 AI', 'aidso', NULL, 'aidso:DYAI', true, true, 2, 120, true, '{"aidso_name": "DYAI"}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('aidso_wenxin_web', '文心一言', 'aidso', NULL, 'aidso:WXYY', true, true, 2, 120, true, '{"aidso_name": "WXYY"}'::jsonb);

UPDATE alembic_version SET version_num='geo_monitoring_0007' WHERE alembic_version.version_num = 'geo_monitoring_0006';

-- Running upgrade geo_monitoring_0007 -> geo_monitoring_0008

ALTER TABLE geo_metric_snapshot ADD COLUMN brand_id BIGINT;

ALTER TABLE geo_metric_snapshot ADD FOREIGN KEY(brand_id) REFERENCES geo_brand (id) ON DELETE SET NULL;

DROP INDEX uq_geo_metric_snapshot_dimension;

CREATE UNIQUE INDEX uq_geo_metric_snapshot_dimension ON geo_metric_snapshot (project_id, run_id, metric_code, coalesce(platform_code, ''), coalesce(prompt_id, -1), coalesce(brand_id, -1));

CREATE INDEX ix_geo_metric_snapshot_brand_trend ON geo_metric_snapshot (project_id, brand_id, metric_code, platform_code, snapshot_at);

UPDATE alembic_version SET version_num='geo_monitoring_0008' WHERE alembic_version.version_num = 'geo_monitoring_0007';

-- Running upgrade geo_monitoring_0008 -> geo_monitoring_0009

ALTER TABLE geo_monitor_project ADD COLUMN monitoring_paused BOOLEAN DEFAULT false NOT NULL;

UPDATE alembic_version SET version_num='geo_monitoring_0009' WHERE alembic_version.version_num = 'geo_monitoring_0008';

-- Running upgrade geo_monitoring_0009 -> geo_monitoring_0010

CREATE TABLE geo_project_draft (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITHOUT TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    draft_key VARCHAR(128), 
    current_step INTEGER DEFAULT '1' NOT NULL, 
    project_data JSONB DEFAULT '{}' NOT NULL, 
    monitor_setup_data JSONB DEFAULT '{}' NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_geo_project_draft_current_step CHECK (current_step >= 1 AND current_step <= 3)
);

CREATE INDEX ix_geo_project_draft_key_updated ON geo_project_draft (draft_key, updated_at);

UPDATE alembic_version SET version_num='geo_monitoring_0010' WHERE alembic_version.version_num = 'geo_monitoring_0009';

-- Running upgrade geo_monitoring_0010 -> geo_monitoring_0011

ALTER TABLE geo_monitor_run DROP CONSTRAINT ck_geo_monitor_run_collection_source;

ALTER TABLE geo_monitor_run ADD CONSTRAINT ck_geo_monitor_run_collection_source CHECK (collection_source IN ('official', 'aidso', 'molizhishu'));

ALTER TABLE geo_monitor_run ADD COLUMN provider_mode_by_platform JSONB DEFAULT '{}' NOT NULL;

ALTER TABLE geo_monitor_run ADD COLUMN provider_screenshot INTEGER DEFAULT '0' NOT NULL;

ALTER TABLE geo_monitor_run ADD COLUMN provider_callback_url VARCHAR(500);

ALTER TABLE geo_monitor_run ADD COLUMN region_code VARCHAR(32);

ALTER TABLE geo_query_task ADD COLUMN provider_name VARCHAR(64);

ALTER TABLE geo_query_task ADD COLUMN provider_task_id VARCHAR(128);

ALTER TABLE geo_query_task ADD COLUMN provider_subtask_id VARCHAR(128);

ALTER TABLE geo_query_task ADD COLUMN provider_platform_code VARCHAR(64);

ALTER TABLE geo_query_task ADD COLUMN provider_mode VARCHAR(64);

ALTER TABLE geo_query_task ADD COLUMN provider_status VARCHAR(64);

ALTER TABLE geo_query_task ADD COLUMN provider_result_json JSONB;

ALTER TABLE geo_query_task ADD COLUMN provider_error_message TEXT;

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('molizhishu_deepseek_web', 'DeepSeek 网页端', 'molizhishu', NULL, 'molizhishu:deepseek', true, true, 2, 120, true, '{"molizhishu_platform": "deepseek", "base_platform": "deepseek", "endpoint_type": "web", "default_mode": "reasoning_search", "supported_modes": ["standard", "reasoning", "search", "reasoning_search"]}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('molizhishu_deepseek_mobile', 'DeepSeek 手机端', 'molizhishu', NULL, 'molizhishu:deepseek_mobile', true, true, 2, 120, true, '{"molizhishu_platform": "deepseek_mobile", "base_platform": "deepseek", "endpoint_type": "app", "default_mode": "reasoning_search", "supported_modes": ["standard", "reasoning", "search", "reasoning_search"]}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('molizhishu_doubao_web', '豆包网页端', 'molizhishu', NULL, 'molizhishu:doubao', true, true, 2, 120, true, '{"molizhishu_platform": "doubao", "base_platform": "doubao", "endpoint_type": "web", "default_mode": "search", "supported_modes": ["standard", "search"]}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('molizhishu_doubao_mobile', '豆包手机端', 'molizhishu', NULL, 'molizhishu:doubao_mobile', true, true, 2, 120, true, '{"molizhishu_platform": "doubao_mobile", "base_platform": "doubao", "endpoint_type": "app", "default_mode": "search", "supported_modes": ["standard", "search"]}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('molizhishu_yuanbao_web', '腾讯元宝', 'molizhishu', NULL, 'molizhishu:yuanbao', true, true, 2, 120, true, '{"molizhishu_platform": "yuanbao", "base_platform": "yuanbao", "endpoint_type": "web", "default_mode": "search", "supported_modes": ["standard", "search"]}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('molizhishu_kimi_web', 'Kimi', 'molizhishu', NULL, 'molizhishu:kimi', true, true, 2, 120, true, '{"molizhishu_platform": "kimi", "base_platform": "kimi", "endpoint_type": "web", "default_mode": "search", "supported_modes": ["standard", "search"]}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('molizhishu_qianwen_web', '通义千问', 'molizhishu', NULL, 'molizhishu:qianwen', true, true, 2, 120, true, '{"molizhishu_platform": "qianwen", "base_platform": "qianwen", "endpoint_type": "web", "default_mode": "search", "supported_modes": ["standard", "search"]}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('molizhishu_quark_web', '夸克 AI', 'molizhishu', NULL, 'molizhishu:quark', true, true, 2, 120, true, '{"molizhishu_platform": "quark", "base_platform": "quark", "endpoint_type": "web", "default_mode": "search", "supported_modes": ["standard", "search"]}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('molizhishu_baiduai_web', '百度 AI+', 'molizhishu', NULL, 'molizhishu:baiduai', true, true, 2, 120, true, '{"molizhishu_platform": "baiduai", "base_platform": "baiduai", "endpoint_type": "web", "default_mode": "search", "supported_modes": ["standard", "search"]}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('molizhishu_weibo_zhisou_web', '微博智搜', 'molizhishu', NULL, 'molizhishu:weibo_zhisou', true, true, 2, 120, true, '{"molizhishu_platform": "weibo_zhisou", "base_platform": "weibo_zhisou", "endpoint_type": "web", "default_mode": "search", "supported_modes": ["standard", "search"]}'::jsonb);

INSERT INTO geo_ai_platform (platform_code, platform_name, adapter_type, base_url, model_name, search_enabled, citation_supported, max_concurrency, timeout_seconds, enabled, extra_config) VALUES ('molizhishu_wenxinyiyan_web', '文心一言', 'molizhishu', NULL, 'molizhishu:wenxinyiyan', true, true, 2, 120, true, '{"molizhishu_platform": "wenxinyiyan", "base_platform": "wenxinyiyan", "endpoint_type": "web", "default_mode": "search", "supported_modes": ["standard", "search"]}'::jsonb);

UPDATE alembic_version SET version_num='geo_monitoring_0011' WHERE alembic_version.version_num = 'geo_monitoring_0010';

-- Running upgrade geo_monitoring_0011 -> geo_monitoring_0012

CREATE TABLE geo_provider_batch (
    id BIGSERIAL NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL, 
    deleted_at TIMESTAMP WITHOUT TIME ZONE, 
    is_deleted BOOLEAN DEFAULT false NOT NULL, 
    tenant_id BIGINT, 
    created_by BIGINT, 
    updated_by BIGINT, 
    run_id BIGINT NOT NULL, 
    provider_name VARCHAR(64) NOT NULL, 
    provider_task_id VARCHAR(128), 
    batch_no INTEGER NOT NULL, 
    status VARCHAR(32) DEFAULT 'pending' NOT NULL, 
    total_items INTEGER DEFAULT '0' NOT NULL, 
    completed_items INTEGER DEFAULT '0' NOT NULL, 
    failed_items INTEGER DEFAULT '0' NOT NULL, 
    submitted_at TIMESTAMP WITH TIME ZONE, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    raw_submit_json JSONB, 
    raw_status_json JSONB, 
    raw_result_json JSONB, 
    error_message TEXT, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_geo_provider_batch_status CHECK (status IN ('pending', 'submitted', 'processing', 'completed', 'partial_completed', 'failed', 'cancelled')), 
    CONSTRAINT ck_geo_provider_batch_total_items CHECK (total_items >= 0), 
    CONSTRAINT ck_geo_provider_batch_completed_items CHECK (completed_items >= 0), 
    CONSTRAINT ck_geo_provider_batch_failed_items CHECK (failed_items >= 0), 
    FOREIGN KEY(run_id) REFERENCES geo_monitor_run (id) ON DELETE CASCADE, 
    CONSTRAINT uq_geo_provider_batch_run_no UNIQUE (run_id, batch_no)
);

CREATE INDEX ix_geo_provider_batch_run_status ON geo_provider_batch (run_id, status);

CREATE INDEX ix_geo_provider_batch_provider_task ON geo_provider_batch (provider_name, provider_task_id);

ALTER TABLE geo_query_task ADD COLUMN provider_batch_id BIGINT;

ALTER TABLE geo_query_task ADD CONSTRAINT fk_geo_query_task_provider_batch_id FOREIGN KEY(provider_batch_id) REFERENCES geo_provider_batch (id) ON DELETE SET NULL;

UPDATE alembic_version SET version_num='geo_monitoring_0012' WHERE alembic_version.version_num = 'geo_monitoring_0011';

-- Running upgrade geo_monitoring_0012 -> geo_monitoring_0013

CREATE INDEX ix_geo_monitor_project_tenant ON geo_monitor_project (tenant_id);

CREATE INDEX ix_geo_monitor_run_tenant ON geo_monitor_run (tenant_id);

CREATE INDEX ix_geo_report_tenant ON geo_report (tenant_id);

UPDATE alembic_version SET version_num='geo_monitoring_0013' WHERE alembic_version.version_num = 'geo_monitoring_0012';

-- Running upgrade geo_monitoring_0013 -> geo_monitoring_0014

ALTER TABLE geo_monitor_project ADD COLUMN deep_thinking_enabled_by_platform JSON DEFAULT '{}' NOT NULL;

ALTER TABLE geo_monitor_project ADD COLUMN search_enabled_by_platform JSON DEFAULT '{}' NOT NULL;

UPDATE alembic_version SET version_num='geo_monitoring_0014' WHERE alembic_version.version_num = 'geo_monitoring_0013';

COMMIT;

