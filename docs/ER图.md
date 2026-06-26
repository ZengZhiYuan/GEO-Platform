# GEO-Platform 数据库 ER 图

```mermaid
erDiagram
  GEO_MONITOR_PROJECT {
    bigint id PK
  }
  GEO_BRAND {
    bigint id PK
    bigint project_id FK
  }
  GEO_BRAND_ALIAS {
    bigint id PK
    bigint brand_id FK
  }
  GEO_PROMPT_SET {
    bigint id PK
    bigint project_id FK
  }
  GEO_CORE_KEYWORD {
    bigint id PK
    bigint project_id FK
  }
  GEO_PROMPT {
    bigint id PK
    bigint prompt_set_id FK
    bigint core_keyword_id FK "nullable"
  }
  GEO_PROMPT_LIBRARY {
    bigint id PK
    string prompt_code UK
  }
  GEO_AI_PLATFORM {
    bigint id PK
    string platform_code UK
  }
  GEO_MONITOR_RUN {
    bigint id PK
    bigint project_id FK
    bigint prompt_set_id FK
  }
  GEO_QUERY_TASK {
    bigint id PK
    bigint run_id FK
    bigint prompt_id FK
    string platform_code FK
  }
  GEO_ANSWER {
    bigint id PK
    bigint task_id FK_UK
    string platform_code FK
    bigint prompt_id FK
  }
  GEO_ANSWER_CITATION {
    bigint id PK
    bigint answer_id FK
  }
  GEO_ANSWER_BRAND_RESULT {
    bigint id PK
    bigint answer_id FK
    bigint brand_id FK
  }
  GEO_MONITOR_SCHEDULE {
    bigint id PK
    bigint project_id FK
  }
  GEO_AGENT_EXECUTION {
    bigint id PK
    bigint run_id FK
    string platform_code "logical only"
  }
  GEO_PLATFORM_ANALYSIS {
    bigint id PK
    bigint run_id FK
    string platform_code FK
  }
  GEO_METRIC_SNAPSHOT {
    bigint id PK
    bigint project_id FK
    bigint run_id FK
    bigint brand_id FK "nullable"
    bigint prompt_id FK "nullable"
    string platform_code "logical only"
  }
  GEO_PROMPT_COMPETITIVENESS {
    bigint id PK
    bigint run_id FK
    bigint prompt_id FK
    string platform_code FK
  }
  GEO_SOURCE_STAT {
    bigint id PK
    bigint run_id FK
    string platform_code "logical only"
  }
  GEO_REPORT {
    bigint id PK
    bigint project_id FK
    bigint run_id FK
  }

  GEO_MONITOR_PROJECT ||--o{ GEO_BRAND : "geo_brand.project_id -> geo_monitor_project.id"
  GEO_BRAND ||--o{ GEO_BRAND_ALIAS : "geo_brand_alias.brand_id -> geo_brand.id"
  GEO_MONITOR_PROJECT ||--o{ GEO_PROMPT_SET : "geo_prompt_set.project_id -> geo_monitor_project.id"
  GEO_MONITOR_PROJECT ||--o{ GEO_CORE_KEYWORD : "geo_core_keyword.project_id -> geo_monitor_project.id"
  GEO_PROMPT_SET ||--o{ GEO_PROMPT : "geo_prompt.prompt_set_id -> geo_prompt_set.id"
  GEO_CORE_KEYWORD ||--o{ GEO_PROMPT : "geo_prompt.core_keyword_id -> geo_core_keyword.id; nullable SET NULL"

  GEO_MONITOR_PROJECT ||--o{ GEO_MONITOR_RUN : "geo_monitor_run.project_id -> geo_monitor_project.id"
  GEO_PROMPT_SET ||--o{ GEO_MONITOR_RUN : "geo_monitor_run.prompt_set_id -> geo_prompt_set.id"
  GEO_MONITOR_RUN ||--o{ GEO_QUERY_TASK : "geo_query_task.run_id -> geo_monitor_run.id"
  GEO_PROMPT ||--o{ GEO_QUERY_TASK : "geo_query_task.prompt_id -> geo_prompt.id"
  GEO_AI_PLATFORM ||--o{ GEO_QUERY_TASK : "geo_query_task.platform_code -> geo_ai_platform.platform_code"

  GEO_QUERY_TASK ||--o| GEO_ANSWER : "geo_answer.task_id -> geo_query_task.id; UNIQUE"
  GEO_AI_PLATFORM ||--o{ GEO_ANSWER : "geo_answer.platform_code -> geo_ai_platform.platform_code"
  GEO_PROMPT ||--o{ GEO_ANSWER : "geo_answer.prompt_id -> geo_prompt.id"
  GEO_ANSWER ||--o{ GEO_ANSWER_CITATION : "geo_answer_citation.answer_id -> geo_answer.id"
  GEO_ANSWER ||--o{ GEO_ANSWER_BRAND_RESULT : "geo_answer_brand_result.answer_id -> geo_answer.id"
  GEO_BRAND ||--o{ GEO_ANSWER_BRAND_RESULT : "geo_answer_brand_result.brand_id -> geo_brand.id"

  GEO_MONITOR_PROJECT ||--o{ GEO_MONITOR_SCHEDULE : "geo_monitor_schedule.project_id -> geo_monitor_project.id"
  GEO_MONITOR_RUN ||--o{ GEO_AGENT_EXECUTION : "geo_agent_execution.run_id -> geo_monitor_run.id"
  GEO_MONITOR_RUN ||--o{ GEO_PLATFORM_ANALYSIS : "geo_platform_analysis.run_id -> geo_monitor_run.id"
  GEO_AI_PLATFORM ||--o{ GEO_PLATFORM_ANALYSIS : "geo_platform_analysis.platform_code -> geo_ai_platform.platform_code"

  GEO_MONITOR_PROJECT ||--o{ GEO_METRIC_SNAPSHOT : "geo_metric_snapshot.project_id -> geo_monitor_project.id"
  GEO_MONITOR_RUN ||--o{ GEO_METRIC_SNAPSHOT : "geo_metric_snapshot.run_id -> geo_monitor_run.id"
  GEO_BRAND ||--o{ GEO_METRIC_SNAPSHOT : "geo_metric_snapshot.brand_id -> geo_brand.id; nullable SET NULL"
  GEO_PROMPT ||--o{ GEO_METRIC_SNAPSHOT : "geo_metric_snapshot.prompt_id -> geo_prompt.id; nullable SET NULL"

  GEO_MONITOR_RUN ||--o{ GEO_PROMPT_COMPETITIVENESS : "geo_prompt_competitiveness.run_id -> geo_monitor_run.id"
  GEO_PROMPT ||--o{ GEO_PROMPT_COMPETITIVENESS : "geo_prompt_competitiveness.prompt_id -> geo_prompt.id"
  GEO_AI_PLATFORM ||--o{ GEO_PROMPT_COMPETITIVENESS : "geo_prompt_competitiveness.platform_code -> geo_ai_platform.platform_code"

  GEO_MONITOR_RUN ||--o{ GEO_SOURCE_STAT : "geo_source_stat.run_id -> geo_monitor_run.id"
  GEO_MONITOR_PROJECT ||--o{ GEO_REPORT : "geo_report.project_id -> geo_monitor_project.id"
  GEO_MONITOR_RUN ||--o{ GEO_REPORT : "geo_report.run_id -> geo_monitor_run.id"
  ...
```