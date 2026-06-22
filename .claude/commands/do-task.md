请执行用户指定的任务编号。

执行规则：

1. 只执行该任务编号，不要扩展范围
2. **Superpowers：** 先 Read `using-superpowers` skill；涉及代码则 Read `test-driven-development`；多步骤可先 Read `writing-plans` / `brainstorming`（见 `.cursor/rules/superpowers-dev-workflow.mdc`）
3. 开始前先阅读相关 docs（V2 Task 先读 `docs/AI应用监测_MVP_V2_Task索引.md` + 对应章节）
4. 先输出实现计划
5. 测试先行，再编码
6. 编码后运行可用验证命令；收尾前 Read `verification-before-completion` 并用输出证明通过
7. 若改动源码：在仓库根目录 `codegraph sync`
8. 更新 docs/progress.md
9. 输出修改文件列表
10. 输出下一步建议任务编号

任务描述不清楚时，先提出风险，不要盲目开发。
