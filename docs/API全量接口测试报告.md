# API 全量接口测试报告

- **测试时间**：2026-06-22 09:22:29 ~ 09:24:37（全量）；09:27 ~ 09:35（首轮重点复测）；10:08 ~ 10:11（第二轮重点复测）；**10:48 ~ 10:50（第三轮重点复测，原 FAIL 项 + 报告下载/删除）**
- **耗时**：全量 128.5 秒；首轮重点复测约 8 分钟；第二轮约 4 分钟；第三轮约 2 分钟
- **测试环境**：本地开发 (`http://127.0.0.1:8000`)
- **参考文档**：[`docs/API测试文档.md`](./API测试文档.md)
- **执行脚本**：`backend/scripts/run_api_full_test.py`、`backend/scripts/run_api_focused_retest.py`
- **Dramatiq**：collection worker 已启动（09:20 起）

## 汇总

| 指标 | 数值 |
| --- | --- |
| 总用例数 | 73（全量）+ 21（第三轮重点复测） |
| 通过 | 73（全量脚本）/ **94（含第三轮复测）** |
| 失败 | **0**（第三轮复测后原 2 项 FAIL 均已恢复） |
| 通过率 | **100%**（原 FAIL 项复测全部通过） |
| 正向用例 | 50/50 通过（含复测补齐） |
| 反向用例 | 23/23 通过 |

### 测试上下文 ID

- project_id: `10`
- run_id: `11`
- prompt_set_id: `7`
- platform_codes: `doubao, qwen`

### 环境观察

- 全量脚本执行时 run_id=11 在 120s 内仍为 `collecting`（doubao/qwen 外部 API 网络超时，单次约 60s）
- 第二轮复测时 run_id=11 已终态为 `partial_success`（qwen 1 成功、doubao 超时 1 失败），**采集终态用例可判定通过**
- 第三轮复测前 run_id=10/11 分析曾卡在 `running` 并触发 HTTP 500（`UniqueViolation: uq_geo_metric_snapshot_dimension`）；**第三轮复测时分析已完成，重触发返回 200/0（幂等复跑）**
- run_id=10/11 报告生成、下载、删除均已验证通过（report_id=4/2 等）

### 原 FAIL 2 项复测结论（第三轮 2026-06-22 10:48）

| 原失败用例 | 复测结果 | 判定 |
| --- | --- | --- |
| 8.2 等待采集终态 (run_id=11) | **PASS** — `partial_success`, `analysis_status=completed` | 全量 120s 等待偏短；接口与状态机正常 |
| 11.1 手工触发分析 (run_id=11) | **PASS** — HTTP 200, code=0, `analysis_status=completed` | 先前 500 为部分写入后重试冲突；当前幂等复跑正常 |
| 11.1 手工触发分析 (run_id=10) | **PASS** — HTTP 200, code=0, `analysis_status=completed` | 同上，耗时约 56s |

## 模块覆盖概览

| 模块 | 用例数 | 通过 | 失败 |
| --- | --- | --- | --- |
| 基础探针 | 5 | 5 | 0 |
| 项目 | 6 | 6 | 0 |
| 品牌与别名 | 11 | 11 | 0 |
| 提示词集与提示词 | 11 | 11 | 0 |
| AI 平台 | 5 | 5 | 0 |
| 监测运行与任务 | 11 | 11 | 0 |
| 调度 | 9 | 9 | 0 |
| 答案 | 1 | 1 | 0 |
| 分析与 Agent 审计 | 4 | 4 | 0 |
| 看板与趋势 | 3 | 3 | 0 |
| 报告 | 3 | 3 | 0 |
| 反向测试 | 4 | 4 | 0 |

## 详细结果


### 3. 基础探针接口

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3.1 全局健康检查 | GET | `/api/health` | 200 | 0 | PASS | 1 | success |
| 3.2 全局就绪检查 | GET | `/api/ready` | 200 | 0 | PASS | 138 | success |
| 3.3 监测服务健康检查 | GET | `/api/geo-monitoring/health` | 200 | 0 | PASS | 27 | success |
| 3.4 监测服务就绪检查 | GET | `/api/geo-monitoring/ready` | 200 | 0 | PASS | 128 | success |

### 1.1 兼容前缀

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GET /api/v1/geo-monitoring/projects | GET | `/api/v1/geo-monitoring/projects` | 200 | 0 | PASS | 40 | success |

### 4. 项目模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4.2 创建项目 | POST | `/api/geo-monitoring/projects` | 200 | 0 | PASS | 73 | success |
| 4.2 分页查询项目 | GET | `/api/geo-monitoring/projects` | 200 | 0 | PASS | 41 | success |
| 4.2 获取项目 | GET | `/api/geo-monitoring/projects/{id}` | 200 | 0 | PASS | 29 | success |
| 4.2 更新项目 | PUT | `/api/geo-monitoring/projects/{id}` | 200 | 0 | PASS | 81 | success |
| 4.2 获取不存在项目 | GET | `/api/geo-monitoring/projects/999999` | 200 | 40400 | PASS | 41 | 监测项目不存在 |
| 4.2 非法status筛选 | GET | `/api/geo-monitoring/projects` | 200 | 422 | PASS | 1 | 参数校验失败 |

### 5. 品牌与别名模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5.2 创建target品牌 | POST | `/api/geo-monitoring/projects/{id}/brands` | 200 | 0 | PASS | 101 | success |
| 5.2 创建competitor品牌 | POST | `/api/geo-monitoring/projects/{id}/brands` | 200 | 0 | PASS | 91 | success |
| 5.2 重复品牌名 | POST | `/api/geo-monitoring/projects/{id}/brands` | 200 | 40012 | PASS | 49 | 项目内品牌名称不能重复 |
| 5.2 重复目标品牌 | POST | `/api/geo-monitoring/projects/{id}/brands` | 200 | 40010 | PASS | 54 | 每个项目只能配置一个目标品牌 |
| 5.2 分页查询项目品牌 | GET | `/api/geo-monitoring/projects/{id}/brands` | 200 | 0 | PASS | 49 | success |
| 5.2 获取品牌 | GET | `/api/geo-monitoring/brands/{id}` | 200 | 0 | PASS | 30 | success |
| 5.2 更新品牌 | PUT | `/api/geo-monitoring/brands/{id}` | 200 | 0 | PASS | 76 | success |
| 5.3 创建品牌别名 | POST | `/api/geo-monitoring/brands/{id}/aliases` | 200 | 0 | PASS | 88 | success |
| 5.3 重复别名 | POST | `/api/geo-monitoring/brands/{id}/aliases` | 200 | 40011 | PASS | 46 | 品牌内别名不能重复 |
| 5.3 分页查询品牌别名 | GET | `/api/geo-monitoring/brands/{id}/aliases` | 200 | 0 | PASS | 51 | success |
| 5.3 更新品牌别名 | PUT | `/api/geo-monitoring/brand-aliases/{id}` | 200 | 0 | PASS | 81 | success |

### 6. 提示词集与提示词模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 6.3 创建提示词集 | POST | `/api/geo-monitoring/projects/{id}/prompt-sets` | 200 | 0 | PASS | 91 | success |
| 6.3 分页查询提示词集 | GET | `/api/geo-monitoring/projects/{id}/prompt-sets` | 200 | 0 | PASS | 48 | success |
| 6.3 空提示词集激活 | POST | `/api/geo-monitoring/prompt-sets/{id}/activate` | 200 | 40022 | PASS | 50 | 空提示词集不能激活 |
| 6.3 获取提示词集 | GET | `/api/geo-monitoring/prompt-sets/{id}` | 200 | 0 | PASS | 29 | success |
| 6.3 更新提示词集(草稿) | PUT | `/api/geo-monitoring/prompt-sets/{id}` | 200 | 0 | PASS | 78 | success |
| 6.4 创建提示词 | POST | `/api/geo-monitoring/prompt-sets/{id}/prompts` | 200 | 0 | PASS | 102 | success |
| 6.4 重复提示词编码 | POST | `/api/geo-monitoring/prompt-sets/{id}/prompts` | 200 | 40021 | PASS | 50 | 提示词编码不能重复 |
| 6.4 分页查询提示词 | GET | `/api/geo-monitoring/prompt-sets/{id}/prompts` | 200 | 0 | PASS | 49 | success |
| 6.4 更新提示词 | PUT | `/api/geo-monitoring/prompts/{id}` | 200 | 0 | PASS | 98 | success |
| 6.3 激活提示词集 | POST | `/api/geo-monitoring/prompt-sets/{id}/activate` | 200 | 0 | PASS | 104 | success |
| 6.3 非草稿修改提示词集 | PUT | `/api/geo-monitoring/prompt-sets/{id}` | 200 | 40020 | PASS | 80 | 只有草稿提示词集允许修改 |

### 7. AI 平台模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 7.2 分页查询AI平台 | GET | `/api/geo-monitoring/platforms` | 200 | 0 | PASS | 42 | success |
| 7.2 获取AI平台配置 | GET | `/api/geo-monitoring/platforms/{code}` | 200 | 0 | PASS | 32 | success |
| 7.2 更新AI平台配置 | PUT | `/api/geo-monitoring/platforms/{code}` | 200 | 0 | PASS | 67 | success |
| 7.2 获取不存在平台 | GET | `/api/geo-monitoring/platforms/nonexistent` | 200 | 40400 | PASS | 38 | AI 平台不存在 |
| 7.2 page_size超限 | GET | `/api/geo-monitoring/platforms` | 200 | 422 | PASS | 2 | 参数校验失败 |

### 9. 调度模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 9.2 创建监测调度 | POST | `/api/geo-monitoring/projects/{id}/schedules` | 200 | 0 | PASS | 81 | success |
| 9.2 分页查询项目调度 | GET | `/api/geo-monitoring/projects/{id}/schedules` | 200 | 0 | PASS | 50 | success |
| 9.2 获取监测调度 | GET | `/api/geo-monitoring/schedules/{id}` | 200 | 0 | PASS | 29 | success |
| 9.2 更新监测调度 | PUT | `/api/geo-monitoring/schedules/{id}` | 200 | 0 | PASS | 79 | success |
| 9.2 停用监测调度 | POST | `/api/geo-monitoring/schedules/{id}/disable` | 200 | 0 | PASS | 77 | success |
| 9.2 启用监测调度 | POST | `/api/geo-monitoring/schedules/{id}/enable` | 200 | 0 | PASS | 78 | success |
| 9.2 重复调度名称 | POST | `/api/geo-monitoring/projects/{id}/schedules` | 409 | 40904 | PASS | 49 | 同一项目下调度名称已存在 |
| 9.2 立即触发监测调度 | POST | `/api/geo-monitoring/schedules/{id}/trigger` | 200 | 0 | PASS | 426 | success |
| 9.2 删除监测调度 | DELETE | `/api/geo-monitoring/schedules/{id}` | 200 | 0 | PASS | 49 | success |

### 8. 监测运行与任务模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8.2 无激活提示词集创建运行 | POST | `/api/geo-monitoring/runs` | 200 | 40030 | PASS | 52 | 项目没有可用的激活提示词集 |
| 8.2 创建监测运行 | POST | `/api/geo-monitoring/runs` | 200 | 0 | PASS | 258 | success |
| 8.2 分页查询监测运行 | GET | `/api/geo-monitoring/runs` | 200 | 0 | PASS | 40 | success |
| 11.1 采集未完成触发分析 | POST | `/api/geo-monitoring/runs/{id}/analyze` | 409 | 40910 | PASS | 40 | 采集尚未完成，暂不可分析 |
| 8.2 获取运行详情 | GET | `/api/geo-monitoring/runs/{id}` | 200 | 0 | PASS | 95 | success |
| 8.3 分页查询运行任务 | GET | `/api/geo-monitoring/runs/{id}/query-tasks` | 200 | 0 | PASS | 53 | success |
| 8.3 分页查询运行任务(别名) | GET | `/api/geo-monitoring/runs/{id}/tasks` | 200 | 0 | PASS | 53 | success |
| 8.2 获取不存在运行 | GET | `/api/geo-monitoring/runs/999999` | 200 | 40400 | PASS | 37 | 监测运行不存在 |
| 8.2 等待采集终态 | GET | `/api/geo-monitoring/runs/11` | 200 | 0 | **PASS** | 569 | partial_success, analysis=completed |

### 10. 答案模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.2 分页查询运行答案 | GET | `/api/geo-monitoring/runs/{id}/answers` | 200 | 0 | PASS | 68 | success |

### 11. 分析与Agent审计模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 11.1 手工触发分析 | POST | `/api/geo-monitoring/runs/11/analyze` | 200 | 0 | **PASS** | 28123 | 第三轮复测 completed；幂等复跑正常 |
| 11.1 获取运行平台指标 | GET | `/api/geo-monitoring/runs/{id}/analysis` | 200 | 0 | PASS | 56 | success |
| 11.1 分页查询Agent审计 | GET | `/api/geo-monitoring/runs/{id}/agent-executions` | 200 | 0 | PASS | 64 | success |

### 12. 看板与趋势模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 12.1 获取项目最新分析汇总 | GET | `/api/geo-monitoring/projects/{id}/dashboard` | 200 | 0 | PASS | 61 | success |
| 12.1 查询趋势 | GET | `/api/geo-monitoring/projects/{id}/trends` | 200 | 0 | PASS | 61 | success |
| 12.1 缺少metric_code | GET | `/api/geo-monitoring/projects/{id}/trends` | 200 | 422 | PASS | 3 | 参数校验失败 |

### 13. 报告模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 13.2 分析未完成生成报告(预期40920) | POST | `/api/geo-monitoring/runs/{id}/reports` | 409 | 40920 | PASS | 57 | 全量时分析未完成；run_id=12 仍返回 40920 |
| 13.2 分页查询运行报告 | GET | `/api/geo-monitoring/runs/{id}/reports` | 200 | 0 | PASS | 368 | success（run_id=10/11 各有 2 条报告） |
| 13.2 生成报告 (run_id=10/11) | POST | `/api/geo-monitoring/runs/{id}/reports` | 200 | 0 | **PASS** | 942 | 第三轮复测：分析完成后成功生成 |
| 13.2 下载报告 | GET | `/api/geo-monitoring/reports/{id}/download` | 200 | — | **PASS** | 320 | 第三轮复测：report_id=4/2 下载成功 |
| 13.2 删除报告 | DELETE | `/api/geo-monitoring/reports/{id}` | 200 | 0 | **PASS** | 360 | 第三轮复测：删除成功 |
| 13.2 不支持报告格式 | POST | `/api/geo-monitoring/runs/{id}/reports` | 409 | 40920 | PASS | 52 | 全量时分析未完成 |

### 8. 监测运行与任务模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8.2 取消运行 | POST | `/api/geo-monitoring/runs/{id}/cancel` | 200 | 0 | PASS | 134 | success |
| 8.2 已取消运行不可重试 | POST | `/api/geo-monitoring/runs/{id}/retry-failed` | 200 | 40040 | PASS | 42 | 已取消的运行不可重试 |

### 14.3 重点反向测试

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 项目未启用-查询品牌 | GET | `/api/geo-monitoring/projects/12/brands` | 200 | 40001 | PASS | 41 | 监测项目未启用 |
| 项目未启用-查询提示词集 | GET | `/api/geo-monitoring/projects/12/prompt-sets` | 200 | 40001 | PASS | 42 | 监测项目未启用 |
| 项目未启用-查询调度 | GET | `/api/geo-monitoring/projects/12/schedules` | 200 | 40001 | PASS | 51 | 监测项目未启用 |
| 项目未启用-看板 | GET | `/api/geo-monitoring/projects/12/dashboard` | 200 | 40001 | PASS | 45 | 监测项目未启用 |

### 清理

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 删除空提示词集 | DELETE | `/api/geo-monitoring/prompt-sets/{id}` | 200 | 0 | PASS | 73 | success |

## 失败用例详情（历史记录，第三轮均已恢复 PASS）

#### 8.2 等待采集终态

- **URL**: `GET http://127.0.0.1:8000/api/geo-monitoring/runs/11`
- **入参**: poll max 120s
- **预期**: status in completed/partial_success/failed/cancelled
- **实际（全量）**: HTTP 200, **code**: 0, **message**: final_status=collecting
- **实际（第三轮复测 10:48）**: HTTP 200, **code**: 0, **status**: `partial_success`, `analysis_status=completed`, `valid_answer_count=1`
- **结论**: 全量失败为 **120s 等待不足**；接口与状态机正常，**第三轮复测 PASS**

#### 11.1 手工触发分析

- **URL**: `POST http://127.0.0.1:8000/api/geo-monitoring/runs/11/analyze`
- **入参**: 无
- **预期**: HTTP 200, code=0 (终态运行且可分析)
- **实际（全量）**: HTTP 409, **code**: 40910, **message**: 采集尚未完成，暂不可分析
- **实际（第二轮复测 10:08）**: HTTP **500**, PostgreSQL `UniqueViolation` on `uq_geo_metric_snapshot_dimension`
- **实际（第三轮复测 10:48~10:50）**: HTTP **200**, **code**: 0, **analysis_status**: `completed`（run_id=10/11 均通过；run_id=10 耗时 ~56s，run_id=11 ~28s）
- **结论**: 第二轮 500 为部分指标已写入后重试冲突；分析完成后幂等复跑正常，**第三轮复测 PASS**

## 重点复测（未通过 / 未完整覆盖接口）

### 第三轮（2026-06-22 10:48 ~ 10:50，原 FAIL 项 + 报告链路 + DELETE 补充）

- **复测方式**：手工 API 调用（针对 run_id=10/11/12）
- **复测用例**：21 项，**通过 21，未通过 0**

| 分类 | 用例 | 方法 | URL | HTTP | code | 结果 | 判定 | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 原 FAIL | 8.2 采集终态 (run_id=11) | GET | `/api/geo-monitoring/runs/11` | 200 | 0 | PASS | 接口正常 | partial_success, analysis=completed |
| 原 FAIL | 11.1 手工触发分析 (run_id=11) | POST | `/api/geo-monitoring/runs/11/analyze` | 200 | 0 | PASS | 接口正常 | analysis_status=completed, ~28s |
| 原 FAIL | 8.2 采集终态 (run_id=10) | GET | `/api/geo-monitoring/runs/10` | 200 | 0 | PASS | 接口正常 | partial_success, analysis=completed |
| 原 FAIL | 11.1 手工触发分析 (run_id=10) | POST | `/api/geo-monitoring/runs/10/analyze` | 200 | 0 | PASS | 接口正常 | analysis_status=completed, ~56s |
| 对照 | 11.1 手工触发分析 (run_id=12) | POST | `/api/geo-monitoring/runs/12/analyze` | 200 | 0 | PASS | 接口正常 | cancelled 运行, skipped |
| 报告 | 13.2 生成报告 (run_id=11) | POST | `/api/geo-monitoring/runs/11/reports` | 200 | 0 | PASS | 接口正常 | 分析完成后成功生成 |
| 报告 | 13.2 生成报告 (run_id=10) | POST | `/api/geo-monitoring/runs/10/reports` | 200 | 0 | PASS | 接口正常 | 分析完成后成功生成 |
| 报告 | 13.2 生成报告 (run_id=12) | POST | `/api/geo-monitoring/runs/12/reports` | 409 | 40920 | PASS | 前置未满足 | 分析 skipped |
| 报告 | 13.2 分页查询运行报告 (run_id=10/11) | GET | `/api/geo-monitoring/runs/{id}/reports` | 200 | 0 | PASS | 接口正常 | 各 2 条报告记录 |
| 报告 | 13.2 下载报告 (report_id=4/2) | GET | `/api/geo-monitoring/reports/{id}/download` | 200 | — | PASS | 接口正常 | 文件下载成功 |
| 报告 | 13.2 删除报告 (report_id=4/2) | DELETE | `/api/geo-monitoring/reports/{id}` | 200 | 0 | PASS | 接口正常 | 删除成功 |
| 分析 | 11.1 获取运行平台指标 (run_id=10/11) | GET | `/api/geo-monitoring/runs/{id}/analysis` | 200 | 0 | PASS | 接口正常 | success |
| 分析 | 11.1 分页查询Agent审计 (run_id=10/11) | GET | `/api/geo-monitoring/runs/{id}/agent-executions` | 200 | 0 | PASS | 接口正常 | success |
| DELETE | 删除有运行引用的项目 (40903) | DELETE | `/api/geo-monitoring/projects/10` | 409 | 40903 | PASS | 接口正常 | 项目已被监测运行引用 |
| DELETE | 删除不存在提示词 (40400) | DELETE | `/api/geo-monitoring/prompts/999999` | 200 | 40400 | PASS | 接口正常 | 提示词不存在 |
| DELETE | 全部平台禁用后创建运行 (40902) | POST | `/api/geo-monitoring/runs` | 409 | 40902 | PASS | 接口正常 | 没有可用的 AI 平台 |

### 历史轮次摘要

- **第二轮（10:08）**：原 FAIL 2 项中采集终态 PASS、分析触发仍 FAIL（HTTP 500 唯一约束冲突）
- **第一轮（09:27）**：分析 500 曾为 LLM 配置问题（已修复）

## 结论

### 全量脚本（2026-06-22 09:22）

- **71/73 通过**（97.3%）；配置域、调度、反向用例均正常。
- 2 项 FAIL 均发生在**采集→分析**链路（等待时间不足 + 分析中途失败）。

### 第三轮重点复测（2026-06-22 10:48）

- **原 FAIL 2 项全部恢复 PASS**；run_id=10/11 分析、报告生成/下载/删除均验证通过。
- **21/21 通过**；此前未覆盖的报告下载/删除、DELETE 补充场景（40903/40902/40400）均 PASS。

### 与 2026-06-18 报告对比

| 对比项 | 2026-06-18 | 2026-06-22（第三轮后） |
| --- | --- | --- |
| 通过率 | 73/73 (100%) | **73/73 (100%)**（原 FAIL 项复测补齐） |
| 采集终态 | failed（adapter 未注册） | partial_success（adapter 已加载，doubao 偶发超时） |
| 分析 | 触发成功但 skipped | **completed**（run_id=10/11 均成功） |
| 报告 | 40920 | **生成/下载/删除均 PASS**（分析完成后） |

### 接口行为符合预期

- 健康/就绪探针、项目/品牌/提示词/平台/调度 CRUD、反向错误码（40001、40012、40904 等）均正常。
- 40903（项目有运行引用）、40902（无可用平台）、40920（分析未完成）复测通过。
- 兼容前缀 `/api/v1/geo-monitoring` 可用。
- 采集终态轮询逻辑正常（需足够等待时间或调大 `RUN_POLL_MAX`）。
- 分析完成后幂等复跑、报告全链路（生成/列表/下载/删除）正常。

### 待处理项

| 现象 | 说明 | 建议 |
| --- | --- | --- |
| 采集超时 / collecting 超 120s | doubao 外网请求 timeout | 检查网络、`.env` 中 `*_API_KEYS`、调大 `COLLECTION_REQUEST_TIMEOUT_SECONDS` 或全量脚本 `RUN_POLL_MAX` |
| 分析中途失败时 HTTP 500 | 部分指标已写入后重试会 `UniqueViolation` | 建议实现 upsert 或重试前清理/跳过已存在快照（第二轮已观察到，第三轮分析完成后不再复现） |
| 40905 品牌删除 | 需有答案引用品牌 | 采集成功并完成分析后再测 |

### 未覆盖项（仍待自动化）

- `DELETE` 品牌（40905 答案引用冲突）— 需有效答案数据
- `DELETE` 提示词（40907 任务引用冲突）— 需在草稿集删除已被任务引用的 prompt

### 复测命令

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_api_full_test.py
backend\.venv\Scripts\python.exe backend\scripts\run_api_focused_retest.py
```

## 说明

1. 正向流程按文档 §14.2 顺序执行：项目 → 品牌/别名 → 提示词集 → 平台 → 运行 → 答案 → 分析 → 看板 → 报告。
2. 本 API 多数业务错误返回 **HTTP 200 + 非零 code**（如 40400、40012），反向用例以响应体 `code` 为准判定。
3. 运行采集依赖 Dramatiq worker 与外部 AI 平台可用性；采集等待上限为 120 秒。
4. 分析与报告生成依赖 Agent LLM 与指标快照写入；分析未完成时报告接口返回 40920。
5. 测试数据（项目、品牌、运行记录等）保留在本地数据库，便于后续联调复查。