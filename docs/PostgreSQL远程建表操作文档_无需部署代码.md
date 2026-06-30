# PostgreSQL 远程建表操作文档（无需部署代码）

适用范围：GEO-Platform 后端当前 Alembic 迁移链，目标版本 `geo_monitoring_0013`。

本文档面向**尚未将项目代码部署到服务器、但已通过 Navicat 等工具连上远程 PostgreSQL** 的场景。你只需：

1. 在本地开发机生成建表 SQL 文件 `docs/geo-platform_schema.sql`（仓库中可能已有）；
2. 在 **Navicat 查询窗口** 中对该 SQL 执行一次；
3. 按本文档验收表结构与种子数据。

服务器上**不需要**安装本仓库、Python 或 Alembic。

与直接在服务器执行 Alembic 的方式不同：后者假设代码已部署到服务器并运行 `alembic upgrade head`；本文档以 **Navicat + 本地 SQL 文件** 完成建表。

---

## 1. 关于 `geo-platform_schema.sql` 的重要说明

### 1.1 文件中有什么

该文件由本地命令 `alembic upgrade head --sql` 生成，内容仅为 PostgreSQL **结构 DDL**，例如：

- `CREATE TABLE` / `CREATE INDEX` / `ALTER TABLE`
- 外键、唯一约束、检查约束
- `INSERT INTO geo_ai_platform` 默认平台种子数据
- `alembic_version` 版本记录

### 1.2 文件中没有什么（这是正常现象）

当前 Alembic 迁移**未定义** PostgreSQL 元数据注释，因此 SQL 中**不包含**：

- `COMMENT ON TABLE ...`
- `COMMENT ON COLUMN ...`

因此在 Navicat 中：

- **「设计表」里的「注释」列为空**，并不代表建表失败；
- 表名、字段名仍可从 SQL 或本文档 **附录 A** 对照理解；
- 若希望在 Navicat 里看到中文备注，需另行手工维护注释，或后续由 DBA 补充 `COMMENT ON` 语句（不影响应用运行）。

### 1.3 中文默认值/种子数据可能乱码

在 Windows 下生成 SQL 时，若终端编码不是 UTF-8，`geo_ai_platform.platform_name`、`geo_monitor_project.industry` 等中文内容可能出现乱码（如 `璞嗗寘` 而非 `豆包`）。

**处理方式（任选其一）：**

- 重新按第 3 节用 UTF-8 生成 SQL；或
- 建表完成后，在 Navicat 中执行第 5.2 节的修正 SQL。

---

## 2. 整体流程

```text
本地开发机                              你已通过 Navicat 连接的远程库
──────────                              ────────────────────────────
（可选）重新生成 geo-platform_schema.sql
  ↓
Navicat 打开该 SQL 并执行        ──→    空库 geo-platform 创建 23 张表
  ↓                                     写入 alembic_version
（可选）修正中文种子数据
  ↓
Navicat 查询窗口验收
  ↓
本地 .env 指向同一远程库，开始联调
```

建表过程**不依赖 Redis** 和 **Nacos**。本地生成 SQL 时，Alembic 会加载应用配置，需临时提供 `DATABASE_URL` 与 `REDIS_URL`（可为占位值，不要求数据库真实可达）。

---

## 3. Navicat 连接前置检查

你已完成 Navicat 连接时，执行建表前请确认：

| 检查项 | 说明 |
|--------|------|
| 连接可用 | Navicat 能正常打开目标连接，无超时或认证失败 |
| 目标数据库 | 选中待建表的库（下文示例库名为 `geo-platform`） |
| 空库 | `public` schema 下**尚无业务表**；若已有同名表，不要重复执行全量 SQL |
| 账号权限 | 当前用户能对 `public` schema 执行 `CREATE TABLE`；若无权限，请 DBA 执行授权 SQL（见 3.1） |

### 3.1 库名含连字符时的注意点

若数据库名包含 `-`（如 `geo-platform`），在 SQL 中须用**双引号**：

```sql
CREATE DATABASE "geo-platform" OWNER geo_app ENCODING 'UTF8';
```

Navicat 图形界面创建数据库时不受此限制；仅在手写 SQL 时需注意。

若库和用户尚未创建，可在 Navicat「查询」窗口用管理员账号执行：

```sql
CREATE USER geo_app WITH PASSWORD '<强密码>';
CREATE DATABASE "geo-platform" OWNER geo_app ENCODING 'UTF8';
GRANT ALL PRIVILEGES ON DATABASE "geo-platform" TO geo_app;

\c "geo-platform"
GRANT USAGE, CREATE ON SCHEMA public TO geo_app;
ALTER SCHEMA public OWNER TO geo_app;
```

> Navicat 若不支持 `\c`，请切换到 `geo-platform` 连接后再执行 `GRANT` 语句。

---

## 4. 本地生成或更新 SQL 文件（可选）

若 `docs/geo-platform_schema.sql` 已存在且迁移版本未变，可跳过本节，直接进入第 5 节。

### 4.1 前置条件

- 已克隆本仓库；
- 已安装 `backend/.venv` 及依赖。

```powershell
# Windows PowerShell，仓库根目录
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
```

### 4.2 生成命令

请将 `<pgsql-host>`、`<URL编码后的密码>` 替换为实际值：

```powershell
chcp 65001 > $null
$env:PYTHONIOENCODING = 'utf-8'
$env:DATABASE_URL = 'postgresql+psycopg2://geo_app:<URL编码后的密码>@<pgsql-host>:5432/geo-platform'
$env:REDIS_URL = 'redis://127.0.0.1:6379/0'

backend\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini heads
backend\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head --sql 2>$null |
  Set-Content -Path docs\geo-platform_schema.sql -Encoding utf8
```

预期：

- `heads` 输出 `geo_monitoring_0013 (head)`；
- SQL 文件约 830 行，以 `BEGIN;` 开头、`COMMIT;` 结尾；
- 含 `INSERT INTO geo_ai_platform` 与 `geo_monitoring_0013` 版本更新。

---

## 5. 使用 Navicat 执行建表

### 5.1 执行步骤

1. 在 Navicat 左侧选中目标连接下的 **`geo-platform`** 数据库；
2. 菜单 **查询 → 新建查询**（或右键数据库 → **新建查询**）；
3. 点击 **打开** / **载入**，选择仓库文件 `docs/geo-platform_schema.sql`；
4. 确认脚本首尾为 `BEGIN;` 与 `COMMIT;`（整脚本在一个事务中，失败会整体回滚）；
5. 点击 **运行**（或 `F5` / `Ctrl+R`）；
6. 执行成功后，在左侧 **表** 节点上 **右键 → 刷新**。

### 5.2 修正 AI 平台中文名称（若出现乱码）

建表完成后，在 Navicat 查询窗口执行：

```sql
UPDATE geo_ai_platform SET platform_name = '豆包'    WHERE platform_code = 'doubao';
UPDATE geo_ai_platform SET platform_name = '通义千问' WHERE platform_code = 'qwen';
UPDATE geo_ai_platform SET platform_name = '腾讯元宝' WHERE platform_code = 'yuanbao';
UPDATE geo_ai_platform SET platform_name = 'DeepSeek' WHERE platform_code = 'deepseek';
UPDATE geo_ai_platform SET platform_name = 'Kimi'     WHERE platform_code = 'kimi';
UPDATE geo_ai_platform SET platform_name = '豆包 Web 端'        WHERE platform_code = 'aidso_doubao_web';
UPDATE geo_ai_platform SET platform_name = '豆包 App 端'        WHERE platform_code = 'aidso_doubao_app';
UPDATE geo_ai_platform SET platform_name = 'DeepSeek Web 端'    WHERE platform_code = 'aidso_deepseek_web';
UPDATE geo_ai_platform SET platform_name = 'DeepSeek App 端'    WHERE platform_code = 'aidso_deepseek_app';
UPDATE geo_ai_platform SET platform_name = 'Kimi Web 端'        WHERE platform_code = 'aidso_kimi_web';
UPDATE geo_ai_platform SET platform_name = '元宝 Web 端'        WHERE platform_code = 'aidso_yuanbao_web';
UPDATE geo_ai_platform SET platform_name = '元宝 App 端'        WHERE platform_code = 'aidso_yuanbao_app';
UPDATE geo_ai_platform SET platform_name = '千问 Web 端'        WHERE platform_code = 'aidso_qwen_web';
UPDATE geo_ai_platform SET platform_name = '千问 App 端'        WHERE platform_code = 'aidso_qwen_app';
UPDATE geo_ai_platform SET platform_name = '百度 AI'             WHERE platform_code = 'aidso_baidu_web';
UPDATE geo_ai_platform SET platform_name = '抖音 AI'             WHERE platform_code = 'aidso_douyin_web';
UPDATE geo_ai_platform SET platform_name = '文心一言'            WHERE platform_code = 'aidso_wenxin_web';
UPDATE geo_ai_platform SET platform_name = 'DeepSeek 网页端'     WHERE platform_code = 'molizhishu_deepseek_web';
UPDATE geo_ai_platform SET platform_name = 'DeepSeek 手机端'     WHERE platform_code = 'molizhishu_deepseek_mobile';
UPDATE geo_ai_platform SET platform_name = '豆包网页端'          WHERE platform_code = 'molizhishu_doubao_web';
UPDATE geo_ai_platform SET platform_name = '豆包手机端'          WHERE platform_code = 'molizhishu_doubao_mobile';
UPDATE geo_ai_platform SET platform_name = '腾讯元宝'            WHERE platform_code = 'molizhishu_yuanbao_web';
UPDATE geo_ai_platform SET platform_name = 'Kimi'                WHERE platform_code = 'molizhishu_kimi_web';
UPDATE geo_ai_platform SET platform_name = '通义千问'            WHERE platform_code = 'molizhishu_qianwen_web';
UPDATE geo_ai_platform SET platform_name = '夸克 AI'             WHERE platform_code = 'molizhishu_quark_web';
UPDATE geo_ai_platform SET platform_name = '百度 AI+'            WHERE platform_code = 'molizhishu_baiduai_web';
UPDATE geo_ai_platform SET platform_name = '微博智搜'            WHERE platform_code = 'molizhishu_weibo_zhisou_web';
UPDATE geo_ai_platform SET platform_name = '文心一言'            WHERE platform_code = 'molizhishu_wenxinyiyan_web';
```

### 5.3 执行注意

- 只对**空库**执行全量脚本；
- 若报错 `relation already exists`，说明库中已有表，需先备份后清库或联系 DBA；
- 执行账号必须是第 3 节中有 `CREATE` 权限的用户（如 `geo_app`）。

---

## 6. Navicat 验收

在 Navicat **查询** 窗口依次执行以下 SQL。

### 6.1 Alembic 版本

```sql
SELECT version_num FROM alembic_version;
```

预期：`geo_monitoring_0013`

### 6.2 表数量

```sql
SELECT count(*) AS table_count
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
```

预期：`23`（22 张业务表 + `alembic_version`）

### 6.3 业务表清单

```sql
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
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
geo_core_keyword
geo_metric_snapshot
geo_monitor_project
geo_monitor_run
geo_monitor_schedule
geo_platform_analysis
geo_prompt
geo_prompt_competitiveness
geo_prompt_library
geo_prompt_set
geo_project_draft
geo_provider_batch
geo_query_task
geo_report
geo_source_stat
```

也可在 Navicat 左侧展开 **表**，目视确认上述表均存在。

### 6.4 默认 AI 平台种子数据

```sql
SELECT platform_code, platform_name, adapter_type
FROM geo_ai_platform
ORDER BY platform_code;
```

预期 28 条：官方平台 5 条（`deepseek`、`doubao`、`kimi`、`qwen`、`yuanbao`）、历史 Aidso 只读兼容平台 12 条、模力指数平台 11 条，且 `platform_name` 中文正常。

---

## 7. 本地联调配置

建表完成后，在仓库根目录 `.env` 中将 `DATABASE_URL` 指向**同一远程库**（与 Navicat 连接信息一致）：

```dotenv
DATABASE_URL=postgresql+psycopg2://geo_app:<URL编码后的密码>@<pgsql-host>:5432/geo-platform
REDIS_URL=redis://:<redis-password>@<redis-host>:6379/0
```

此后可在本地启动 API / worker 进行联调，仍无需把代码部署到 PostgreSQL 服务器。

---

## 8. 迁移版本更新后

当仓库 Alembic head 升级时：

1. 拉取最新代码并更新 `backend/.venv`；
2. 重新执行第 4 节生成新的 `geo-platform_schema.sql`；
3. 对**新的空库**在 Navicat 中再次执行；已有业务数据的库勿重复执行全量 SQL。

---

## 9. 常见问题

### Navicat 里表/字段「注释」为空

见第 1.2 节。结构 DDL 不含 `COMMENT ON`；字段含义见 **附录 A**，或在 Navicat 设计表中手工填写备注。

### `Field required: DATABASE_URL` / `REDIS_URL`

本地生成 SQL 前未设置环境变量，见第 4.2 节。

### 执行报 `permission denied for schema public`

用管理员在目标库执行第 3.1 节 `GRANT` / `ALTER SCHEMA` 后重试。

### 执行报 `relation already exists`

目标库非空。无业务数据时可删库重建；有数据时勿直接重跑全量 SQL。

### 中文乱码

见第 1.3 节与第 5.2 节修正 SQL。

### 已有部分表但没有 `alembic_version`

勿直接执行全量 SQL。先备份，核对结构后再决定清库重建或 `alembic stamp`（生产库慎用）。

---

## 10. 回滚说明

新库建表失败且无业务数据：在 Navicat 或管理员账号下删除并重建数据库，再从第 5 节执行。

生产库或已有数据的库，不要直接 `DROP DATABASE`；先备份再评估。

---

## 11. 后续代码部署到服务器

正式部署后，服务器上也可使用 `alembic upgrade head` 做增量迁移。若远程库已通过本文档建好且 `alembic_version = geo_monitoring_0013`，首次部署不会重复建表；后续新增迁移只会从当前版本向后执行。

---

## 附录 A：表与字段说明（供 Navicat 对照）

以下说明对应 `geo-platform_schema.sql` 将创建的表结构。所有业务表均继承一组**公共字段**（`alembic_version` 除外）。

### A.1 公共字段（业务表通用）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键，自增 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |
| deleted_at | TIMESTAMPTZ | 软删除时间，未删除时为 NULL |
| is_deleted | BOOLEAN | 是否已软删除，默认 false |
| tenant_id | BIGINT | 租户 ID，预留 |
| created_by | BIGINT | 创建人 ID，预留 |
| updated_by | BIGINT | 更新人 ID，预留 |

---

### A.2 配置域（迁移 geo_monitoring_0001）

#### alembic_version

| 字段 | 说明 |
|------|------|
| version_num | 当前 Alembic 迁移版本号，预期 `geo_monitoring_0013` |

#### geo_monitor_project — 监测项目

| 字段 | 说明 |
|------|------|
| project_name | 项目名称 |
| industry | 所属行业，默认「文旅演艺」 |
| description | 项目描述 |
| timezone | 时区，默认 Asia/Shanghai |
| status | 状态：`active` / `disabled` / `archived` |
| official_domain | 官方域名 |
| report_title | 报告标题 |
| report_subtitle | 报告副标题 |
| default_platform_codes | 项目默认平台列表（JSONB，监测设置保存） |
| monitoring_paused | 是否暂停监测，暂停后禁止创建新 Run |

#### geo_brand — 品牌

| 字段 | 说明 |
|------|------|
| project_id | 所属项目 ID |
| brand_name | 品牌名称 |
| brand_type | 类型：`target`（目标，每项目唯一）/ `competitor` / `candidate` |
| official_domain | 品牌官方域名 |
| description | 品牌描述 |
| status | 状态：`active` / `disabled` |

#### geo_brand_alias — 品牌别名

| 字段 | 说明 |
|------|------|
| brand_id | 所属品牌 ID |
| alias_name | 别名文本 |
| match_mode | 匹配模式：`exact` / `contains` / `context` |
| is_ambiguous | 是否歧义别名 |
| context_keywords | 上下文关键词（JSONB 数组） |
| enabled | 是否启用 |

#### geo_prompt_set — Prompt 集（版本）

| 字段 | 说明 |
|------|------|
| project_id | 所属项目 ID |
| set_name | Prompt 集名称 |
| version_no | 版本号 |
| status | 状态：`draft` / `active` / `archived`（每项目仅一个 active） |
| prompt_count | Prompt 数量 |
| checksum | 内容校验和 |
| activated_at | 激活时间 |

#### geo_prompt — 监测问题

| 字段 | 说明 |
|------|------|
| prompt_set_id | 所属 Prompt 集 ID |
| prompt_code | Prompt 编码，集内唯一 |
| prompt_text | 问题正文 |
| prompt_type | 问题类型，默认 generic |
| scene_tag | 场景标签 |
| contains_brand | 问题是否包含品牌词 |
| core_keyword_id | 关联核心词，可为空 |
| enabled | 是否启用 |
| sort_order | 排序 |
| content_hash | 内容哈希 |

#### geo_ai_platform — AI 平台配置

| 字段 | 说明 |
|------|------|
| platform_code | 平台编码（主业务引用键），如 doubao、qwen |
| platform_name | 平台显示名称 |
| adapter_type | 适配器类型：openai_compatible / tencent 等 |
| base_url | API 基础地址 |
| model_name | 默认模型名 |
| search_enabled | 是否启用联网搜索 |
| citation_supported | 是否支持引用来源 |
| max_concurrency | 最大并发数 |
| timeout_seconds | 超时秒数 |
| enabled | 是否启用 |
| extra_config | 扩展配置（JSONB） |

种子数据：官方平台 5 条、历史 Aidso 平台 12 条、模力指数平台 11 条，共 28 条。新建第三方采集使用 `collection_source=molizhishu` 与 `molizhishu_*` 平台码；`aidso_*` 仅用于历史数据只读兼容。

#### geo_monitor_run — 监测运行

| 字段 | 说明 |
|------|------|
| run_no | 运行编号，全局唯一 |
| project_id | 项目 ID |
| prompt_set_id | 使用的 Prompt 集 ID |
| prompt_set_version | Prompt 集版本号（趋势对比口径） |
| trigger_type | 触发方式：`manual` / `schedule` / `retry` |
| triggered_by | 触发人 ID |
| status | 总状态：pending → collecting → analyzing → reporting → completed 等 |
| collection_status | 采集阶段状态 |
| analysis_status | 分析阶段状态 |
| report_status | 报告阶段状态 |
| collection_source | 采集来源：`official` / `aidso` / `molizhishu`；新建 Run 禁止 `aidso` |
| aidso_thinking_enabled_by_platform | 历史 Aidso 兼容字段（JSONB） |
| provider_mode_by_platform | 模力指数各平台 mode 配置（JSONB） |
| provider_screenshot | 模力指数截图策略：0 / 1 / 2 |
| provider_callback_url | 模力指数回调地址 |
| region_code | 模力指数区域编码 |
| platform_codes | 参与平台列表（JSONB） |
| expected_query_count | 预期查询数 |
| success_query_count | 成功查询数 |
| failed_query_count | 失败查询数 |
| valid_answer_count | 有效回答数 |
| data_completeness_rate | 数据完整率 |
| total_tasks / succeeded_tasks / failed_tasks / cancelled_tasks | 任务计数 |
| result_json | 运行结果摘要（JSONB） |
| error_message / error_summary | 错误信息 |
| started_at / completed_at / finished_at | 各阶段时间 |

#### geo_query_task — 查询子任务

| 字段 | 说明 |
|------|------|
| run_id | 所属运行 ID |
| prompt_id | Prompt ID |
| platform_code | AI 平台编码 |
| idempotency_key | 幂等键，全局唯一 |
| status | 状态：pending / queued / running / success / failed / cancelled |
| key_slot | API Key 槽位 |
| retry_count / attempt_count / max_attempts | 重试相关 |
| request_json | 请求快照（JSONB） |
| response_http_status | HTTP 状态码 |
| error_code / error_message | 错误信息 |
| latency_ms | 耗时（毫秒） |
| queued_at / started_at / completed_at / finished_at | 时间戳 |
| last_error_code / last_error_message | 最后一次错误 |
| provider_request_id | 平台侧请求 ID |
| provider_name / provider_task_id / provider_subtask_id | 第三方 provider 任务标识 |
| provider_platform_code / provider_mode / provider_status | 第三方平台、模式与状态 |
| provider_result_json / provider_error_message | 第三方原始结果与错误 |
| provider_batch_id | 关联 `geo_provider_batch`，ProviderBatch 启用时有值 |

---

### A.3 采集域（迁移 geo_monitoring_0002）

#### geo_answer — AI 回答

| 字段 | 说明 |
|------|------|
| task_id | 关联查询任务 ID，一对一 |
| platform_code | 平台编码 |
| prompt_id | Prompt ID |
| raw_text | 原始回答文本 |
| normalized_text | 规范化文本 |
| model_name | 实际使用模型 |
| prompt_tokens / completion_tokens / total_tokens | Token 用量 |
| latency_ms | 采集耗时 |
| collected_at | 采集时间 |
| raw_response_json | 原始响应（JSONB，可选） |

#### geo_answer_citation — 回答引用来源

| 字段 | 说明 |
|------|------|
| answer_id | 所属回答 ID |
| citation_no | 引用序号 |
| title | 来源标题 |
| url | 来源 URL |
| domain | 来源域名 |
| source_type | 来源类型 |
| quoted_text | 引用片段 |

#### geo_answer_brand_result — 回答品牌识别结果

| 字段 | 说明 |
|------|------|
| answer_id | 所属回答 ID |
| brand_id | 品牌 ID |
| is_mentioned | 是否提及 |
| mention_count | 提及次数 |
| first_position | 首次出现位置 |
| sentiment | 情感标签 |
| context_json | 上下文证据（JSONB） |

---

### A.4 分析域（迁移 geo_monitoring_0003）

#### geo_agent_execution — Agent 执行记录

| 字段 | 说明 |
|------|------|
| run_id | 运行 ID |
| platform_code | 平台编码，可为空表示全局 Agent |
| agent_code | Agent 编码 |
| status | pending / running / success / failed / skipped |
| schema_version | 输出 Schema 版本 |
| input_snapshot / output_json | 输入输出快照（JSONB） |
| model_provider / model_name | 使用的 LLM |
| prompt_version | Prompt 版本 |
| prompt_tokens / completion_tokens | Token 用量 |
| error_message | 错误信息 |
| started_at / finished_at | 执行时间 |

#### geo_platform_analysis — 平台级分析汇总

| 字段 | 说明 |
|------|------|
| run_id | 运行 ID |
| platform_code | 平台编码 |
| valid_answer_count | 有效回答数 |
| data_completeness_rate | 数据完整率 |
| brand_mention_count / brand_mention_rate | 品牌提及次数/率 |
| brand_first_count / brand_first_rate | 品牌首位次数/率 |
| brand_first_among_mentions_rate | 提及中首位占比 |
| top_competitors | Top 竞品（JSONB） |
| top_sources | Top 来源（JSONB） |
| prompt_competitiveness_summary | Prompt 竞争力摘要（JSONB） |
| improvement_json / summary_json | 改进建议与摘要（JSONB） |
| status | 分析状态 |

#### geo_metric_snapshot — 指标快照

| 字段 | 说明 |
|------|------|
| project_id / run_id | 项目与运行 |
| platform_code | 平台，可为空表示汇总 |
| prompt_id | Prompt，可为空 |
| metric_code | 指标编码 |
| numerator / denominator | 分子/分母 |
| metric_value | 指标值 |
| metric_json | 扩展指标数据（JSONB） |
| snapshot_at | 快照时间 |
| prompt_set_version | Prompt 集版本（趋势可比口径） |
| is_comparable | 是否可用于趋势对比 |
| completeness_rate | 完整率 |

#### geo_prompt_competitiveness — Prompt 竞争力

| 字段 | 说明 |
|------|------|
| run_id / prompt_id / platform_code | 维度键 |
| target_mentioned | 目标品牌是否被提及 |
| target_rank | 目标品牌排名 |
| target_first | 目标是否首位 |
| competitors_json | 竞品表现（JSONB） |
| position_label | 位置标签 |
| competitiveness_score | 竞争力得分 |
| evidence_json | 证据（JSONB） |

#### geo_source_stat — 引用来源统计

| 字段 | 说明 |
|------|------|
| run_id | 运行 ID |
| platform_code | 平台，可为空 |
| domain | 来源域名 |
| source_name | 来源名称 |
| source_type | 来源类型 |
| citation_count | 引用次数 |
| brand_related_count | 品牌相关引用次数 |
| share_rate | 占比 |
| rank_no | 排名 |

---

### A.5 调度与报告（迁移 geo_monitoring_0004）

#### geo_monitor_schedule — 定时监测调度

| 字段 | 说明 |
|------|------|
| project_id | 项目 ID |
| name | 调度名称，项目内唯一 |
| cron_expr | Cron 表达式 |
| timezone | 时区 |
| enabled | 是否启用 |
| next_run_at / last_run_at | 下次/上次执行时间 |
| misfire_policy | 错过策略：`fire_once` / `ignore` |

#### geo_report — 监测报告

| 字段 | 说明 |
|------|------|
| project_id / run_id | 项目与运行 |
| status | pending / generating / completed / failed |
| format | 报告格式：md / html / pdf |
| file_name | 文件名 |
| relative_storage_path | 相对存储路径 |
| file_size | 文件大小（字节） |
| checksum | 文件校验和 |
| error_message | 生成失败原因 |
| completed_at | 完成时间 |

---

### A.6 监测设置与创建向导（迁移 geo_monitoring_0005 / 0010）

#### geo_core_keyword — 项目核心词

| 字段 | 说明 |
|------|------|
| project_id | 所属项目 ID |
| keyword | 核心词，项目内唯一 |
| description | 描述 |
| sort_order | 排序 |
| enabled | 是否启用 |

#### geo_prompt_library — Prompt 词库模板

| 字段 | 说明 |
|------|------|
| prompt_code | 词库编码，全局唯一 |
| prompt_text | 模板问题正文 |
| prompt_type | 问题类型 |
| industry | 适用行业 |
| scene_tag | 场景标签 |
| default_core_keyword | 推荐核心词 |
| enabled | 是否启用 |

#### geo_project_draft — 创建向导草稿

| 字段 | 说明 |
|------|------|
| draft_key | 前端草稿键，可用于无项目 ID 的向导续填 |
| current_step | 当前步骤，1–3 |
| project_data | 项目基础信息草稿（JSONB） |
| monitor_setup_data | 品牌、竞品、核心词、问题、平台选择草稿（JSONB） |

---

### A.7 第三方 ProviderBatch（迁移 geo_monitoring_0012）

#### geo_provider_batch — 模力指数批量任务

| 字段 | 说明 |
|------|------|
| run_id | 所属监测运行 |
| provider_name | provider 名称，当前为 `molizhishu` |
| provider_task_id | provider 主任务 ID |
| batch_no | Run 内批次号，`run_id + batch_no` 唯一 |
| status | `pending` / `submitted` / `processing` / `completed` / `partial_completed` / `failed` / `cancelled` |
| total_items / completed_items / failed_items | 批次内子任务计数 |
| submitted_at / completed_at | 提交与完成时间 |
| raw_submit_json / raw_status_json / raw_result_json | 提交、轮询、回调或结果原文（JSONB） |
| error_message | 批次级错误信息 |

`geo_query_task.provider_batch_id` 指向该表；ProviderBatch 启用时，worker 可按批次提交、轮询和刷新 run/task 聚合。

---

### A.8 租户索引（迁移 geo_monitoring_0013）

`geo_monitor_project.tenant_id`、`geo_monitor_run.tenant_id`、`geo_report.tenant_id` 已分别建立索引，配合业务 Bearer token 的租户隔离查询。`tenant_id` 仍来自公共字段，不需要额外建表。

---

### A.9 表关系概览

```text
geo_monitor_project
  ├── geo_brand → geo_brand_alias
  ├── geo_core_keyword
  ├── geo_prompt_set → geo_prompt
  ├── geo_monitor_schedule
  └── geo_monitor_run
        ├── geo_provider_batch
        ├── geo_query_task → geo_answer → geo_answer_citation
        │                              └── geo_answer_brand_result
        ├── geo_agent_execution
        ├── geo_platform_analysis
        ├── geo_metric_snapshot
        ├── geo_prompt_competitiveness
        ├── geo_source_stat
        └── geo_report

geo_ai_platform ← 被 geo_query_task / geo_answer / geo_platform_analysis 等引用
geo_prompt_library ← 监测设置保存时可作为问题模板来源
geo_project_draft ← 创建向导草稿，按 draft_key 读取/更新，不直接外键关联项目
```

更完整的领域规则见仓库根目录 `AI应用监测_技术开发文档.md` 与 `backend/app/geo_monitoring/models.py`。
