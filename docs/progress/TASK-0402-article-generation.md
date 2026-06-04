# TASK-0402 实现文章生成任务

- 分支：feat/worker-generation
- 范围：仅改动 backend/（新增 app/tasks、app/services/ai_generation；改 services/writing_task.py）；未触碰 frontend/；未接真实大模型；未改既有接口字段名
- 状态：已完成

## 变更要点

- 新增 `app/services/ai_generation/`（AI 内容生成服务，第一版 Mock，decisions 004）：
  - `base.py`：`AIWriter` 抽象基类（generate_title / generate_article / generate）+
    纯数据类 `ArticleContext` / `ArticleResult`（无 DB 依赖，便于「读上下文」与「调 AI」解耦）。
  - `prompt_assembler.py`：标题/正文 Prompt 模板（dev 文档 11.3/11.4），证明上下文被纳入。
  - `mock_writer.py`：`MockAIWriter` 确定性生成（标题含主创作词、正文按 `article_image_count`
    嵌入候选配图、首图作封面）；含失败哨兵 `__fail__` 触发失败路径；`get_ai_writer()` 工厂。
- 新增 `app/tasks/context.py`：`build_article_context(db, article, task)`——只读拼接关键词
  (distill_keywords)、内容分类(group_name)、写作规范(content_rule / title_rule 指令)、
  画像图库(按 image_category_id 取图片 URL)。品牌知识库模块尚未实现，brand_* 暂留空。
- 新增 `app/tasks/article_tasks.py`：`generate_article` actor + 编排 `run_generation`。
  **分 3 段短事务避免长事务调 AI**：Phase1 读上下文(短事务,只读)→关闭；Phase2 调 AI(无事务)；
  Phase3 回写标题/正文/封面、状态置 `pending_review`(短事务,写)；Phase4 聚合大任务。
  失败置 `failed` 并记录 `error_message`。`enqueue_article_generation` / `enqueue_articles` 投递。
- 修改 `app/services/writing_task.py`：`create_writing_task` 提交后投递每个 article 小任务；
  `retry_writing_task` 重置失败小任务并重新投递。`_enqueue_articles` 对 broker 故障容错
  （仅日志，不阻断建任务）。

## 幂等（要求 17）

- article 不存在/已删除 → 忽略；大任务 cancelled → 不写结果、generating 收敛为 failed；
  article 已是 pending_review/normal/disabled → 跳过（防重复消费覆盖）。

## 契约一致性

- article 状态严格用契约枚举：generating/pending_review/normal/disabled/failed；
  生成成功落 `pending_review`（对齐 TASK-0402 目标）。模型无 retry_count/generation_index
  列，按实际模型实现（generation_index 由同任务 id 升序推导，仅用于展示）。

## 实测

- SQLite 内存（BigInteger 编译为 INTEGER）功能测试：成功路径→pending_review、标题/正文/封面
  写入；上下文拼接正确（标题含关键词、按 article_image_count 嵌 2 图、首图作封面）；
  失败路径(__fail__)→failed + error_message；幂等重复消费→skipped 不覆盖；
  取消任务→run_generation 返回 cancelled、article failed。全部通过。

## 备注 / 遗留

- 品牌知识库模块未实现，上下文中 brand_* 预留待接入；详见 [[TASK-0401-redis-worker]]、[[TASK-0403-task-aggregation]]。
