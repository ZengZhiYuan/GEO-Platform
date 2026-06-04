# TASK-0403 大任务状态聚合

- 分支：feat/worker-generation
- 范围：仅改动 backend/（新增 app/tasks/aggregation.py）；未触碰 frontend/；未改既有接口字段名
- 状态：已完成

## 变更要点

- 新增 `app/tasks/aggregation.py`：`refresh_task_status(task_id, session_factory=SessionLocal)`。
  每次小任务状态变更后于**独立短事务**内重新聚合大任务状态。

## 聚合规则

实际 `writing_task` 表**无** total/pending/running/success/failed 计数列（与 dev 文档 10.4
设计不同，以实际模型为准），故采用「按 article.status 实时 COUNT 分组」推导，不写冗余计数列：

- article.status 映射：generating→进行中；failed→失败；pending_review/normal/disabled→已生成成功(done)
- 推导：
  - 进行中 > 0 → `task_status=running` / `article_result_status=generating`
  - 进行中=0 且 failed=0 → `completed` / `all_success`
  - 进行中=0 且 done=0 → `failed` / `failed`
  - 其余（有成功有失败） → `completed` / `partial_success`
- 大任务 `cancelled` 为终态，不被聚合覆盖。

「失败数量」通过 `article_result_status`（partial_success/failed）及各 article 的
`status=failed` 体现（满足要求 14「能体现失败数量或 failed 状态」），无需新增计数列/迁移。

## 失败重试设计（要求 15）

- 框架级：actor `max_retries=ARTICLE_MAX_RETRIES(默认3)` + Dramatiq `Retries` 中间件；
  借 `CurrentMessage` 读取 retries 计数——**仅最后一次重试用尽时**才置 article failed，
  中间重试保持 generating，避免状态抖动。
- 业务级：`POST /api/writing-tasks/{id}/retry` 重置失败小任务为 generating 并重新投递 MQ。

## 实测

- SQLite 内存功能测试：全部成功→completed/all_success；全失败→failed/failed；
  一成一败→completed/partial_success；cancelled 不被覆盖。全部通过。

## 备注 / 遗留

- 详见 [[TASK-0401-redis-worker]]、[[TASK-0402-article-generation]]。
