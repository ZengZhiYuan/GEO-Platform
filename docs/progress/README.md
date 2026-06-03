# 进度分片机制（progress fragments）

> 目的：消除多个 worktree / 分支并发编辑 `docs/progress.md` 造成的反复合并冲突。

## 约定（所有开发终端必须遵守）

1. **开发终端不直接编辑 `docs/progress.md`。**
2. 每个任务在本目录新增**独立分片文件**：`TASK-XXXX-<slug>.md`
   - 例：`TASK-0205-image-library-backend.md`、`TASK-0207-brand-knowledge-backend.md`
   - 一个任务一个文件，文件名带任务号，**互不重名即互不冲突**。
3. 分片文件由该任务分支创建并随分支提交；**只新增、不改别人的分片**。
4. 任务完成后在 `finish-task` / 收尾阶段写入本分片（替代以往“更新 progress.md”那一步）。

## 主控终端职责（合并后）

合并某功能分支到 `main` 后，由主控终端：

1. 读取该分支带来的 `docs/progress/TASK-XXXX-*.md` 分片。
2. 把要点汇总进 `docs/progress.md`（更新「当前阶段 / 已完成 / 待完成 / 下一步建议」等区段）。
3. 将已汇总的分片移动到 `docs/progress/_archive/`（或按需删除），保持本目录只留“未汇总”的分片。
4. 该汇总提交独立于业务合并，信息形如：`docs: 汇总 TASK-XXXX 进度分片`。

## 分片文件模板

复制以下内容到 `TASK-XXXX-<slug>.md`：

```markdown
# TASK-XXXX <任务名>

- 分支：feat/xx-xxx
- 范围：仅改动 backend/（或 frontend/）；未触碰其他模块；未改动既有接口字段名
- 状态：已完成 / 进行中

## 变更要点

- 新增 `path/to/file`：...
- 修改 `path/to/file`：...

## 契约一致性

- 字段/路径严格对齐 `docs/api-contract.md`（唯一权威源）。如与 dev 文档冲突，说明取舍。

## 实测

- 命令与结果：...

## 备注 / 遗留

- 依赖项、待回归项、联调提示等。
```

## 为什么这样能避免冲突

`docs/progress.md` 是“单一热点文件”——每个任务都往里追加，导致几乎每次合并都在同一文件同一区段冲突。改为“一任务一文件”后，不同分支新增的是**不同文件名**，git 自动合并、零冲突；`docs/progress.md` 仅由主控终端串行更新，不再被多分支并发写。
