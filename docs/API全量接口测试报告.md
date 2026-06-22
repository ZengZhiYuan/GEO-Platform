# API 全量接口测试报告

- **测试时间**：2026-06-22 15:09:47 ~ 15:12:00 (本地时区)
- **耗时**：133.2 秒
- **测试环境**：本地开发 (`http://127.0.0.1:8000`)
- **参考文档**：[`docs/API测试文档.md`](./API测试文档.md)
- **执行脚本**：`backend/scripts/run_api_full_test.py`
- **Dramatiq**：collection worker 已启动

## 汇总

| 指标 | 数值 |
| --- | --- |
| 总用例数 | 83 |
| 通过 | 80 |
| 失败 | 3 |
| 通过率 | 96.4% |
| 正向用例 | 56/58 通过 |
| 反向用例 | 24/25 通过 |

### 测试上下文 ID

- project_id: `23`
- run_id: `14`
- prompt_set_id: `16`
- platform_codes: `qwen`

### 环境观察

- 主监测运行终态：`final_status=collecting`（依赖外部 AI 平台密钥与网络）
- 报告生成：分析未完成（40920），报告下载/删除用例未完整执行

## 模块覆盖概览

| 模块 | 用例数 | 通过 | 失败 |
| --- | --- | --- | --- |
| 基础探针 | 5 | 5 | 0 |
| 项目 | 6 | 6 | 0 |
| 品牌与别名 | 11 | 11 | 0 |
| 提示词集与提示词 | 11 | 11 | 0 |
| AI 平台 | 5 | 5 | 0 |
| 监测运行与任务 | 11 | 10 | 1 |
| 调度 | 9 | 9 | 0 |
| 答案 | 2 | 2 | 0 |
| 分析与 Agent 审计 | 4 | 3 | 1 |
| 看板与趋势 | 3 | 3 | 0 |
| 报告 | 3 | 3 | 0 |
| 反向测试 | 4 | 4 | 0 |

## 详细结果


### 3. 基础探针接口

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 3.1 全局健康检查 | GET | `/api/health` | 200 | 0 | PASS | 27 | success |
| 3.2 全局就绪检查 | GET | `/api/ready` | 200 | 0 | PASS | 296 | success |
| 3.3 监测服务健康检查 | GET | `/api/geo-monitoring/health` | 200 | 0 | PASS | 76 | success |
| 3.4 监测服务就绪检查 | GET | `/api/geo-monitoring/ready` | 200 | 0 | PASS | 129 | success |

### 1.1 兼容前缀

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GET /api/v1/geo-monitoring/projects | GET | `/api/v1/geo-monitoring/projects` | 200 | 0 | PASS | 61 | success |

### 4. 项目模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4.2 创建项目 | POST | `/api/geo-monitoring/projects` | 200 | 0 | PASS | 93 | success |
| 4.2 分页查询项目 | GET | `/api/geo-monitoring/projects` | 200 | 0 | PASS | 84 | success |
| 4.2 获取项目 | GET | `/api/geo-monitoring/projects/{id}` | 200 | 0 | PASS | 109 | success |
| 4.2 更新项目 | PUT | `/api/geo-monitoring/projects/{id}` | 200 | 0 | PASS | 110 | success |
| 4.2 获取不存在项目 | GET | `/api/geo-monitoring/projects/999999` | 200 | 40400 | PASS | 52 | 监测项目不存在 |
| 4.2 非法status筛选 | GET | `/api/geo-monitoring/projects` | 200 | 422 | PASS | 23 | 参数校验失败 |

### 5. 品牌与别名模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5.2 创建target品牌 | POST | `/api/geo-monitoring/projects/{id}/brands` | 200 | 0 | PASS | 117 | success |
| 5.2 创建competitor品牌 | POST | `/api/geo-monitoring/projects/{id}/brands` | 200 | 0 | PASS | 116 | success |
| 5.2 重复品牌名 | POST | `/api/geo-monitoring/projects/{id}/brands` | 200 | 40012 | PASS | 67 | 项目内品牌名称不能重复 |
| 5.2 重复目标品牌 | POST | `/api/geo-monitoring/projects/{id}/brands` | 200 | 40010 | PASS | 74 | 每个项目只能配置一个目标品牌 |
| 5.2 分页查询项目品牌 | GET | `/api/geo-monitoring/projects/{id}/brands` | 200 | 0 | PASS | 70 | success |
| 5.2 获取品牌 | GET | `/api/geo-monitoring/brands/{id}` | 200 | 0 | PASS | 51 | success |
| 5.2 更新品牌 | PUT | `/api/geo-monitoring/brands/{id}` | 200 | 0 | PASS | 98 | success |
| 5.3 创建品牌别名 | POST | `/api/geo-monitoring/brands/{id}/aliases` | 200 | 0 | PASS | 105 | success |
| 5.3 重复别名 | POST | `/api/geo-monitoring/brands/{id}/aliases` | 200 | 40011 | PASS | 68 | 品牌内别名不能重复 |
| 5.3 分页查询品牌别名 | GET | `/api/geo-monitoring/brands/{id}/aliases` | 200 | 0 | PASS | 52 | success |
| 5.3 更新品牌别名 | PUT | `/api/geo-monitoring/brand-aliases/{id}` | 200 | 0 | PASS | 102 | success |

### 6. 提示词集与提示词模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 6.3 创建提示词集 | POST | `/api/geo-monitoring/projects/{id}/prompt-sets` | 200 | 0 | PASS | 119 | success |
| 6.3 分页查询提示词集 | GET | `/api/geo-monitoring/projects/{id}/prompt-sets` | 200 | 0 | PASS | 73 | success |
| 6.3 空提示词集激活 | POST | `/api/geo-monitoring/prompt-sets/{id}/activate` | 200 | 40022 | PASS | 79 | 空提示词集不能激活 |
| 6.3 获取提示词集 | GET | `/api/geo-monitoring/prompt-sets/{id}` | 200 | 0 | PASS | 55 | success |
| 6.3 更新提示词集(草稿) | PUT | `/api/geo-monitoring/prompt-sets/{id}` | 200 | 0 | PASS | 93 | success |
| 6.4 创建提示词 | POST | `/api/geo-monitoring/prompt-sets/{id}/prompts` | 200 | 0 | PASS | 124 | success |
| 6.4 重复提示词编码 | POST | `/api/geo-monitoring/prompt-sets/{id}/prompts` | 200 | 40021 | PASS | 65 | 提示词编码不能重复 |
| 6.4 分页查询提示词 | GET | `/api/geo-monitoring/prompt-sets/{id}/prompts` | 200 | 0 | PASS | 78 | success |
| 6.4 更新提示词 | PUT | `/api/geo-monitoring/prompts/{id}` | 200 | 0 | PASS | 117 | success |
| 6.3 激活提示词集 | POST | `/api/geo-monitoring/prompt-sets/{id}/activate` | 200 | 0 | PASS | 102 | success |
| 6.3 非草稿修改提示词集 | PUT | `/api/geo-monitoring/prompt-sets/{id}` | 200 | 40020 | PASS | 67 | 只有草稿提示词集允许修改 |

### 7. AI 平台模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 7.2 分页查询AI平台 | GET | `/api/geo-monitoring/platforms` | 200 | 0 | PASS | 64 | success |
| 7.2 获取AI平台配置 | GET | `/api/geo-monitoring/platforms/{code}` | 200 | 0 | PASS | 49 | success |
| 7.2 更新AI平台配置 | PUT | `/api/geo-monitoring/platforms/{code}` | 200 | 0 | PASS | 86 | success |
| 7.2 获取不存在平台 | GET | `/api/geo-monitoring/platforms/nonexistent` | 200 | 40400 | PASS | 46 | AI 平台不存在 |
| 7.2 page_size超限 | GET | `/api/geo-monitoring/platforms` | 200 | 422 | PASS | 23 | 参数校验失败 |

### 5.4 核心词、Prompt 词库与监测设置

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5.4 分页查询 Prompt 词库 | GET | `/api/geo-monitoring/prompt-library` | 200 | 0 | PASS | 73 | success |
| 5.4 创建核心词 | POST | `/api/geo-monitoring/projects/{id}/core-keywords` | 200 | 0 | PASS | 95 | success |
| 5.4 分页查询核心词 | GET | `/api/geo-monitoring/projects/{id}/core-keywords` | 200 | 0 | PASS | 81 | success |
| 5.4 重复核心词 | POST | `/api/geo-monitoring/projects/{id}/core-keywords` | 200 | 40024 | PASS | 74 | 项目内核心词不能重复 |
| 5.4 更新核心词 | PUT | `/api/geo-monitoring/core-keywords/{id}` | 200 | 0 | PASS | 95 | success |
| 5.4 获取监测设置 | GET | `/api/geo-monitoring/projects/{id}/monitor-setup` | 200 | 0 | PASS | 206 | success |
| 5.4 保存监测设置 | PUT | `/api/geo-monitoring/projects/{id}/monitor-setup` | 200 | 0 | PASS | 606 | success |
| 5.4 保存后再次获取监测设置 | GET | `/api/geo-monitoring/projects/{id}/monitor-setup` | 200 | 0 | PASS | 224 | success |
| 5.4 非法平台编码 | PUT | `/api/geo-monitoring/projects/{id}/monitor-setup` | 200 | 40025 | PASS | 85 | 平台不可用: invalid_platform_code |

### 9. 调度模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 9.2 创建监测调度 | POST | `/api/geo-monitoring/projects/{id}/schedules` | 200 | 0 | PASS | 100 | success |
| 9.2 分页查询项目调度 | GET | `/api/geo-monitoring/projects/{id}/schedules` | 200 | 0 | PASS | 65 | success |
| 9.2 获取监测调度 | GET | `/api/geo-monitoring/schedules/{id}` | 200 | 0 | PASS | 56 | success |
| 9.2 更新监测调度 | PUT | `/api/geo-monitoring/schedules/{id}` | 200 | 0 | PASS | 98 | success |
| 9.2 停用监测调度 | POST | `/api/geo-monitoring/schedules/{id}/disable` | 200 | 0 | PASS | 81 | success |
| 9.2 启用监测调度 | POST | `/api/geo-monitoring/schedules/{id}/enable` | 200 | 0 | PASS | 108 | success |
| 9.2 重复调度名称 | POST | `/api/geo-monitoring/projects/{id}/schedules` | 409 | 40904 | PASS | 79 | 同一项目下调度名称已存在 |
| 9.2 立即触发监测调度 | POST | `/api/geo-monitoring/schedules/{id}/trigger` | 200 | 0 | PASS | 532 | success |
| 9.2 删除监测调度 | DELETE | `/api/geo-monitoring/schedules/{id}` | 200 | 0 | PASS | 71 | success |

### 8. 监测运行与任务模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8.2 无激活提示词集创建运行 | POST | `/api/geo-monitoring/runs` | 200 | 40030 | PASS | 52 | 项目没有可用的激活提示词集 |
| 8.2 创建监测运行 | POST | `/api/geo-monitoring/runs` | 200 | 0 | PASS | 302 | success |
| 8.2 分页查询监测运行 | GET | `/api/geo-monitoring/runs` | 200 | 0 | PASS | 70 | success |
| 11.1 采集未完成触发分析 | POST | `/api/geo-monitoring/runs/{id}/analyze` | 409 | 40910 | PASS | 59 | 采集尚未完成，暂不可分析 |
| 8.2 获取运行详情 | GET | `/api/geo-monitoring/runs/{id}` | 200 | 0 | PASS | 126 | success |
| 8.3 分页查询运行任务 | GET | `/api/geo-monitoring/runs/{id}/query-tasks` | 200 | 0 | PASS | 75 | success |
| 8.3 分页查询运行任务(别名) | GET | `/api/geo-monitoring/runs/{id}/tasks` | 200 | 0 | PASS | 53 | success |
| 8.2 获取不存在运行 | GET | `/api/geo-monitoring/runs/999999` | 200 | 40400 | PASS | 58 | 监测运行不存在 |
| 8.2 等待采集终态 | GET | `/api/geo-monitoring/runs/14` | 200 | 0 | **FAIL** | 0 | final_status=collecting |

### 10. 答案模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.2 分页查询运行答案 | GET | `/api/geo-monitoring/runs/{id}/answers` | 200 | 0 | PASS | 92 | success |
| 10.2 获取答案详情 | GET | `/api/geo-monitoring/answers/{id}` | 200 | 0 | PASS | 99 | success |

### 11. 分析与Agent审计模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 11.1 手工触发分析 | POST | `/api/geo-monitoring/runs/14/analyze` | 409 | 40910 | **FAIL** | 58 | 采集尚未完成，暂不可分析 |
| 11.1 获取运行平台指标 | GET | `/api/geo-monitoring/runs/{id}/analysis` | 200 | 0 | PASS | 72 | success |
| 11.1 分页查询Agent审计 | GET | `/api/geo-monitoring/runs/{id}/agent-executions` | 200 | 0 | PASS | 310 | success |

### 12. 看板与趋势模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 12.1 获取项目最新分析汇总 | GET | `/api/geo-monitoring/projects/{id}/dashboard` | 200 | 0 | PASS | 70 | success |
| 12.1 查询趋势 | GET | `/api/geo-monitoring/projects/{id}/trends` | 200 | 0 | PASS | 54 | success |
| 12.1 缺少metric_code | GET | `/api/geo-monitoring/projects/{id}/trends` | 200 | 422 | PASS | 4 | 参数校验失败 |

### 13. 报告模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 13.2 分析未完成生成报告(预期40920) | POST | `/api/geo-monitoring/runs/{id}/reports` | 409 | 40920 | PASS | 295 | 分析尚未完成，暂不可生成报告 |
| 13.2 分页查询运行报告 | GET | `/api/geo-monitoring/runs/{id}/reports` | 200 | 0 | PASS | 56 | success |
| 13.2 不支持报告格式 | POST | `/api/geo-monitoring/runs/{id}/reports` | 409 | 40920 | PASS | 59 | 分析尚未完成，暂不可生成报告 |

### 8. 监测运行与任务模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8.2 取消运行 | POST | `/api/geo-monitoring/runs/{id}/cancel` | 200 | 0 | PASS | 162 | success |
| 8.2 已取消运行不可重试 | POST | `/api/geo-monitoring/runs/{id}/retry-failed` | 200 | 40040 | PASS | 55 | 已取消的运行不可重试 |

### 14.3 重点反向测试

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 项目未启用-查询品牌 | GET | `/api/geo-monitoring/projects/25/brands` | 200 | 40001 | PASS | 53 | 监测项目未启用 |
| 项目未启用-查询提示词集 | GET | `/api/geo-monitoring/projects/25/prompt-sets` | 200 | 40001 | PASS | 63 | 监测项目未启用 |
| 项目未启用-查询调度 | GET | `/api/geo-monitoring/projects/25/schedules` | 200 | 40001 | PASS | 64 | 监测项目未启用 |
| 项目未启用-看板 | GET | `/api/geo-monitoring/projects/25/dashboard` | 200 | 40001 | PASS | 59 | 监测项目未启用 |

### 清理

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 删除空提示词集 | DELETE | `/api/geo-monitoring/prompt-sets/{id}` | 409 | 40906 | **FAIL** | 75 | 提示词集已被监测运行引用，无法删除 |

## 失败用例详情

#### 8.2 等待采集终态

- **URL**: `GET http://127.0.0.1:8000/api/geo-monitoring/runs/14`
- **入参**: poll max 120s
- **预期**: status in completed/partial_success/failed/cancelled
- **实际 HTTP**: 200, **code**: 0, **message**: final_status=collecting
- **响应摘要**: run_id=14

#### 11.1 手工触发分析

- **URL**: `POST http://127.0.0.1:8000/api/geo-monitoring/runs/14/analyze`
- **入参**: 无
- **预期**: HTTP 200, code=0 (终态运行)
- **实际 HTTP**: 409, **code**: 40910, **message**: 采集尚未完成，暂不可分析
- **响应摘要**: {"code": 40910, "message": "采集尚未完成，暂不可分析", "data": null}

#### 删除空提示词集

- **URL**: `DELETE http://127.0.0.1:8000/api/geo-monitoring/prompt-sets/{id}`
- **入参**: 无
- **预期**: 草稿删除成功
- **实际 HTTP**: 409, **code**: 40906, **message**: 提示词集已被监测运行引用，无法删除
- **响应摘要**: 

## 说明

1. 正向流程按文档 §14.2 顺序执行：项目 → 品牌/别名 → 提示词集 → 平台 → 监测设置 → 运行 → 答案 → 分析 → 看板 → 报告。
2. 本 API 多数业务错误返回 **HTTP 200 + 非零 code**（如 40400、40012），反向用例以响应体 `code` 为准判定。
3. 运行采集依赖 Dramatiq worker 与外部 AI 平台可用性；采集等待上限为 120 秒。
4. 分析与报告生成依赖 Agent LLM 配置；分析未完成时报告接口返回 40920。
5. 测试数据（项目、品牌、运行记录等）保留在本地数据库，便于后续联调复查。
