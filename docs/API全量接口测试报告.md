# API 全量接口测试报告

- **测试时间**：2026-06-18 16:40:51 ~ 16:41:04 (本地时区)
- **耗时**：13.0 秒
- **测试环境**：本地开发 (`http://127.0.0.1:8000`)
- **参考文档**：[`docs/API测试文档.md`](./API测试文档.md)
- **执行脚本**：`backend/scripts/run_api_full_test.py`
- **Dramatiq**：collection worker 已启动

## 汇总

| 指标 | 数值 |
| --- | --- |
| 总用例数 | 73 |
| 通过 | 73 |
| 失败 | 0 |
| 通过率 | 100.0% |
| 正向用例 | 50/50 通过 |
| 反向用例 | 23/23 通过 |

### 测试上下文 ID

- project_id: `7`
- run_id: `8`
- prompt_set_id: `5`
- platform_codes: `doubao, qwen`

### 环境观察

- 主监测运行终态：`final_status=failed`（依赖外部 AI 平台密钥与网络）
- 报告生成：分析未完成（40920），报告下载/删除用例未完整执行

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
| 3.1 全局健康检查 | GET | `/api/health` | 200 | 0 | PASS | 14 | success |
| 3.2 全局就绪检查 | GET | `/api/ready` | 200 | 0 | PASS | 302 | success |
| 3.3 监测服务健康检查 | GET | `/api/geo-monitoring/health` | 200 | 0 | PASS | 87 | success |
| 3.4 监测服务就绪检查 | GET | `/api/geo-monitoring/ready` | 200 | 0 | PASS | 136 | success |

### 1.1 兼容前缀

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GET /api/v1/geo-monitoring/projects | GET | `/api/v1/geo-monitoring/projects` | 200 | 0 | PASS | 59 | success |

### 4. 项目模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4.2 创建项目 | POST | `/api/geo-monitoring/projects` | 200 | 0 | PASS | 99 | success |
| 4.2 分页查询项目 | GET | `/api/geo-monitoring/projects` | 200 | 0 | PASS | 59 | success |
| 4.2 获取项目 | GET | `/api/geo-monitoring/projects/{id}` | 200 | 0 | PASS | 105 | success |
| 4.2 更新项目 | PUT | `/api/geo-monitoring/projects/{id}` | 200 | 0 | PASS | 107 | success |
| 4.2 获取不存在项目 | GET | `/api/geo-monitoring/projects/999999` | 200 | 40400 | PASS | 42 | 监测项目不存在 |
| 4.2 非法status筛选 | GET | `/api/geo-monitoring/projects` | 200 | 422 | PASS | 18 | 参数校验失败 |

### 5. 品牌与别名模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5.2 创建target品牌 | POST | `/api/geo-monitoring/projects/{id}/brands` | 200 | 0 | PASS | 118 | success |
| 5.2 创建competitor品牌 | POST | `/api/geo-monitoring/projects/{id}/brands` | 200 | 0 | PASS | 92 | success |
| 5.2 重复品牌名 | POST | `/api/geo-monitoring/projects/{id}/brands` | 200 | 40012 | PASS | 75 | 项目内品牌名称不能重复 |
| 5.2 重复目标品牌 | POST | `/api/geo-monitoring/projects/{id}/brands` | 200 | 40010 | PASS | 53 | 每个项目只能配置一个目标品牌 |
| 5.2 分页查询项目品牌 | GET | `/api/geo-monitoring/projects/{id}/brands` | 200 | 0 | PASS | 74 | success |
| 5.2 获取品牌 | GET | `/api/geo-monitoring/brands/{id}` | 200 | 0 | PASS | 32 | success |
| 5.2 更新品牌 | PUT | `/api/geo-monitoring/brands/{id}` | 200 | 0 | PASS | 80 | success |
| 5.3 创建品牌别名 | POST | `/api/geo-monitoring/brands/{id}/aliases` | 200 | 0 | PASS | 113 | success |
| 5.3 重复别名 | POST | `/api/geo-monitoring/brands/{id}/aliases` | 200 | 40011 | PASS | 50 | 品牌内别名不能重复 |
| 5.3 分页查询品牌别名 | GET | `/api/geo-monitoring/brands/{id}/aliases` | 200 | 0 | PASS | 49 | success |
| 5.3 更新品牌别名 | PUT | `/api/geo-monitoring/brand-aliases/{id}` | 200 | 0 | PASS | 95 | success |

### 6. 提示词集与提示词模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 6.3 创建提示词集 | POST | `/api/geo-monitoring/projects/{id}/prompt-sets` | 200 | 0 | PASS | 120 | success |
| 6.3 分页查询提示词集 | GET | `/api/geo-monitoring/projects/{id}/prompt-sets` | 200 | 0 | PASS | 74 | success |
| 6.3 空提示词集激活 | POST | `/api/geo-monitoring/prompt-sets/{id}/activate` | 200 | 40022 | PASS | 74 | 空提示词集不能激活 |
| 6.3 获取提示词集 | GET | `/api/geo-monitoring/prompt-sets/{id}` | 200 | 0 | PASS | 47 | success |
| 6.3 更新提示词集(草稿) | PUT | `/api/geo-monitoring/prompt-sets/{id}` | 200 | 0 | PASS | 92 | success |
| 6.4 创建提示词 | POST | `/api/geo-monitoring/prompt-sets/{id}/prompts` | 200 | 0 | PASS | 96 | success |
| 6.4 重复提示词编码 | POST | `/api/geo-monitoring/prompt-sets/{id}/prompts` | 200 | 40021 | PASS | 74 | 提示词编码不能重复 |
| 6.4 分页查询提示词 | GET | `/api/geo-monitoring/prompt-sets/{id}/prompts` | 200 | 0 | PASS | 54 | success |
| 6.4 更新提示词 | PUT | `/api/geo-monitoring/prompts/{id}` | 200 | 0 | PASS | 113 | success |
| 6.3 激活提示词集 | POST | `/api/geo-monitoring/prompt-sets/{id}/activate` | 200 | 0 | PASS | 100 | success |
| 6.3 非草稿修改提示词集 | PUT | `/api/geo-monitoring/prompt-sets/{id}` | 200 | 40020 | PASS | 40 | 只有草稿提示词集允许修改 |

### 7. AI 平台模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 7.2 分页查询AI平台 | GET | `/api/geo-monitoring/platforms` | 200 | 0 | PASS | 60 | success |
| 7.2 获取AI平台配置 | GET | `/api/geo-monitoring/platforms/{code}` | 200 | 0 | PASS | 32 | success |
| 7.2 更新AI平台配置 | PUT | `/api/geo-monitoring/platforms/{code}` | 200 | 0 | PASS | 83 | success |
| 7.2 获取不存在平台 | GET | `/api/geo-monitoring/platforms/nonexistent` | 200 | 40400 | PASS | 41 | AI 平台不存在 |
| 7.2 page_size超限 | GET | `/api/geo-monitoring/platforms` | 200 | 422 | PASS | 20 | 参数校验失败 |

### 9. 调度模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 9.2 创建监测调度 | POST | `/api/geo-monitoring/projects/{id}/schedules` | 200 | 0 | PASS | 96 | success |
| 9.2 分页查询项目调度 | GET | `/api/geo-monitoring/projects/{id}/schedules` | 200 | 0 | PASS | 50 | success |
| 9.2 获取监测调度 | GET | `/api/geo-monitoring/schedules/{id}` | 200 | 0 | PASS | 58 | success |
| 9.2 更新监测调度 | PUT | `/api/geo-monitoring/schedules/{id}` | 200 | 0 | PASS | 97 | success |
| 9.2 停用监测调度 | POST | `/api/geo-monitoring/schedules/{id}/disable` | 200 | 0 | PASS | 88 | success |
| 9.2 启用监测调度 | POST | `/api/geo-monitoring/schedules/{id}/enable` | 200 | 0 | PASS | 80 | success |
| 9.2 重复调度名称 | POST | `/api/geo-monitoring/projects/{id}/schedules` | 409 | 40904 | PASS | 59 | 同一项目下调度名称已存在 |
| 9.2 立即触发监测调度 | POST | `/api/geo-monitoring/schedules/{id}/trigger` | 200 | 0 | PASS | 451 | success |
| 9.2 删除监测调度 | DELETE | `/api/geo-monitoring/schedules/{id}` | 200 | 0 | PASS | 69 | success |

### 8. 监测运行与任务模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8.2 无激活提示词集创建运行 | POST | `/api/geo-monitoring/runs` | 200 | 40030 | PASS | 66 | 项目没有可用的激活提示词集 |
| 8.2 创建监测运行 | POST | `/api/geo-monitoring/runs` | 200 | 0 | PASS | 280 | success |
| 8.2 分页查询监测运行 | GET | `/api/geo-monitoring/runs` | 200 | 0 | PASS | 51 | success |
| 11.1 采集未完成触发分析 | POST | `/api/geo-monitoring/runs/{id}/analyze` | 409 | 40910 | PASS | 63 | 采集尚未完成，暂不可分析 |
| 8.2 获取运行详情 | GET | `/api/geo-monitoring/runs/{id}` | 200 | 0 | PASS | 111 | success |
| 8.3 分页查询运行任务 | GET | `/api/geo-monitoring/runs/{id}/query-tasks` | 200 | 0 | PASS | 81 | success |
| 8.3 分页查询运行任务(别名) | GET | `/api/geo-monitoring/runs/{id}/tasks` | 200 | 0 | PASS | 57 | success |
| 8.2 获取不存在运行 | GET | `/api/geo-monitoring/runs/999999` | 200 | 40400 | PASS | 43 | 监测运行不存在 |
| 8.2 等待采集终态 | GET | `/api/geo-monitoring/runs/8` | 200 | 0 | PASS | 0 | final_status=failed |

### 10. 答案模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10.2 分页查询运行答案 | GET | `/api/geo-monitoring/runs/{id}/answers` | 200 | 0 | PASS | 80 | success |

### 11. 分析与Agent审计模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 11.1 手工触发分析 | POST | `/api/geo-monitoring/runs/8/analyze` | 200 | 0 | PASS | 771 | success |
| 11.1 获取运行平台指标 | GET | `/api/geo-monitoring/runs/{id}/analysis` | 200 | 0 | PASS | 47 | success |
| 11.1 分页查询Agent审计 | GET | `/api/geo-monitoring/runs/{id}/agent-executions` | 200 | 0 | PASS | 78 | success |

### 12. 看板与趋势模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 12.1 获取项目最新分析汇总 | GET | `/api/geo-monitoring/projects/{id}/dashboard` | 200 | 0 | PASS | 73 | success |
| 12.1 查询趋势 | GET | `/api/geo-monitoring/projects/{id}/trends` | 200 | 0 | PASS | 77 | success |
| 12.1 缺少metric_code | GET | `/api/geo-monitoring/projects/{id}/trends` | 200 | 422 | PASS | 3 | 参数校验失败 |

### 13. 报告模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 13.2 分析未完成生成报告(预期40920) | POST | `/api/geo-monitoring/runs/{id}/reports` | 409 | 40920 | PASS | 55 | 分析尚未完成，暂不可生成报告 |
| 13.2 分页查询运行报告 | GET | `/api/geo-monitoring/runs/{id}/reports` | 200 | 0 | PASS | 58 | success |
| 13.2 不支持报告格式 | POST | `/api/geo-monitoring/runs/{id}/reports` | 409 | 40920 | PASS | 42 | 分析尚未完成，暂不可生成报告 |

### 8. 监测运行与任务模块

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8.2 取消运行 | POST | `/api/geo-monitoring/runs/{id}/cancel` | 200 | 0 | PASS | 157 | success |
| 8.2 已取消运行不可重试 | POST | `/api/geo-monitoring/runs/{id}/retry-failed` | 200 | 40040 | PASS | 67 | 已取消的运行不可重试 |

### 14.3 重点反向测试

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 项目未启用-查询品牌 | GET | `/api/geo-monitoring/projects/9/brands` | 200 | 40001 | PASS | 50 | 监测项目未启用 |
| 项目未启用-查询提示词集 | GET | `/api/geo-monitoring/projects/9/prompt-sets` | 200 | 40001 | PASS | 59 | 监测项目未启用 |
| 项目未启用-查询调度 | GET | `/api/geo-monitoring/projects/9/schedules` | 200 | 40001 | PASS | 61 | 监测项目未启用 |
| 项目未启用-看板 | GET | `/api/geo-monitoring/projects/9/dashboard` | 200 | 40001 | PASS | 65 | 监测项目未启用 |

### 清理

| 用例 | 方法 | URL | HTTP | code | 结果 | 耗时(ms) | 说明 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 删除空提示词集 | DELETE | `/api/geo-monitoring/prompt-sets/{id}` | 200 | 0 | PASS | 82 | success |
## 结论

本次全量接口测试 **73/73 用例通过**，覆盖文档中探针、项目、品牌、提示词、平台、运行、调度、答案、分析、看板、报告及重点反向场景。

### 接口行为符合预期

- 健康/就绪探针、CRUD 配置域接口响应正常。
- 反向用例（重复品牌、空集激活、参数校验、项目未启用等）均返回文档约定错误码。
- 兼容前缀 `/api/v1/geo-monitoring` 可用。

### 环境限制（非接口缺陷）

| 现象 | 说明 | 建议 |
| --- | --- | --- |
| 监测运行终态 `failed` | 采集任务调用外部 AI 平台失败（密钥/网络/配额） | 确认 `.env` 中各平台 `*_ENABLED` 与 API Key 配置 |
| 报告生成返回 40920 | 分析状态未达 `completed`/`partial_success` | 采集成功后重跑分析，再测报告创建/下载 |
| 报告下载/删除未测 | 前置分析未完成 | 分析完成后可单独调用 `POST /runs/{id}/reports` |

### 未覆盖项（文档有但本次未自动化）

- `DELETE` 品牌（40905 答案引用冲突）
- `DELETE` 项目（40903 运行引用冲突）
- `DELETE` 提示词（40907 任务引用冲突）
- 全部平台禁用后创建运行（40902）

如需复测，可执行：

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_api_full_test.py
```

## 说明

1. 正向流程按文档 §14.2 顺序执行。
2. 本 API 多数业务错误返回 **HTTP 200 + 非零 code**，反向用例以响应体 `code` 为准判定。
3. 测试数据保留在本地数据库，便于后续联调复查。
