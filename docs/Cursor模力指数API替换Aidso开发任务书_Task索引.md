# Cursor 模力指数 API 替换 Aidso 开发任务书 — Task 索引

> **用途：** 供 Cursor / Agent 快速定位模力指数替换任务章节，避免通读 `Cursor模力指数API替换Aidso开发任务书.md` 全文。  
> **任务书路径：** `docs/Cursor模力指数API替换Aidso开发任务书.md`  
> **适用场景：** 第三方采集接口替换、Aidso 下线、模力指数 API 接入、provider 状态/回调/轮询/拆批等开发任务。

## 执行规则摘要（§2，行 23–40）

- **范围：** 默认只改 `backend` 与 `docs`；前端仅列契约，除非用户明确要求，不改 `frontend/`。
- **默认入口：** 用户输入 `执行 Task M5：Molizhishu Client / Adapter`、`执行 M7` 等 M 系列任务时，默认进入本任务书。
- **读取策略：** 先读本索引，再按行号局部读取任务书；禁止通读无关大型文档。
- **后端环境：** 后端命令必须使用 `backend/.venv`；读取中文文档与命令输出按 UTF-8。
- **测试先行：** 代码 Task 必须先写失败测试，再最小实现。
- **文档同步：** 涉及接口、配置、部署或生命周期说明时，同步 `docs/API接口文档.md`、`docs/API测试文档.md`、`docs/采集任务生命周期说明.md`、`.env.example` / README 等相关文档。
- **CodeGraph：** 改动 `backend/` 源码且验收通过后执行：
  ```powershell
  codegraph status
  codegraph sync
  codegraph status
  ```

## 推荐开发顺序

P0 闭环优先：

```text
M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8 → M13
```

P1 能力增强：

```text
M9 → M10 → M11 → M12 → M14
```

P2 正式版批量化：

```text
M15
```

说明：

- M5 依赖 M1/M2 的配置与平台映射口径。
- M7 依赖 M5/M6 的 adapter、registry 与 key pool。
- M8 依赖 M5/M7 的统一 `PlatformAnswer` 与 pending 元数据。
- M15 是正式版 ProviderBatch，不应阻塞 P0 单 QueryTask 闭环。

## 任务目录

| Task | 标题 | 行号（约） | 优先级 |
| --- | --- | --- | --- |
| — | §1 开发目标 | 10–22 | — |
| — | §2 执行规则 | 23–40 | — |
| — | §3 综合分析与统一决策 | 41–81 | — |
| — | §4 平台映射口径 | 82–105 | — |
| — | §5 Task 索引 | 106–126 | — |
| M0 | 基线、决策记录与测试先行准备 | 129–157 | P0 |
| M1 | 新增模力指数配置项 | 158–197 | P0 |
| M2 | 平台映射与平台种子数据 | 198–232 | P0 |
| M3 | 数据库迁移与 ORM 模型 | 233–278 | P0 |
| M4 | Schema 与创建 Run 契约 | 279–321 | P0 |
| M5 | Molizhishu Client / Adapter | 322–377 | P0 |
| M6 | Registry、KeyPool 与采集凭证接入 | 378–407 | P0 |
| M7 | CollectionService 轮询续跑改造 | 408–452 | P0 |
| M8 | 结果归一化、入库与安全展示 | 453–512 | P0 |
| M9 | Run 路由、取消与停止任务 | 513–549 | P1 |
| M10 | Callback 接口与幂等处理 | 550–588 | P1 |
| M11 | RegionCode 与截图策略 | 589–626 | P1 |
| M12 | 分析、报告与页面聚合回归 | 627–659 | P1 |
| M13 | 测试套件迁移与真实接口 smoke 脚本 | 660–694 | P0/P1 |
| M14 | 文档、部署配置与 Aidso 运行期下线 | 695–731 | P1 |
| M15 | ProviderBatch 批量化正式版能力 | 732–779 | P2 |
| — | §7 状态与错误映射 | 780–814 | — |
| — | §8 MVP 验收标准 | 815–831 | — |
| — | §9 正式版验收标准 | 832–845 | — |
| — | §10 推荐验收命令 | 846–865 | — |
| — | §11 Cursor 推荐指令格式 | 866–879 | — |
| — | §12 风险与处理建议 | 880–末 | — |

## 按 Task 必读章节

| Task | 必读章节 |
| --- | --- |
| M0 | §1、§2、§3、Task M0 |
| M1 | §2、§3.3、Task M1、§10、§12 |
| M2 | §3.3、§4、Task M2、§12 |
| M3 | §3.1、§3.3、Task M3、§7、§10、§12 |
| M4 | §3.3、§4、Task M4、§10、§12 |
| M5 | §3.2、§3.3、§4、Task M5、§7、§10、§12 |
| M6 | §3.1、§3.3、§4、Task M6、§10 |
| M7 | §3.1、§3.2、Task M7、§7、§10、§12 |
| M8 | §3.2、§3.3、Task M8、§7、§10、§12 |
| M9 | §3.3、Task M9、§7、§9、§12 |
| M10 | §3.2、Task M10、§7、§9、§12 |
| M11 | §3.2、Task M11、§9、§12 |
| M12 | §1、§3.3、Task M12、§8、§9 |
| M13 | §2、Task M13、§8、§10、§12 |
| M14 | §2、Task M14、§8、§9、§12 |
| M15 | §3.3、Task M15、§7、§9、§12 |

## 相关文档读取建议

| 场景 | 必读 |
| --- | --- |
| 新增/改造 API | `docs/API接口文档.md` 相关章节 |
| 写接口或采集测试 | `docs/API测试文档.md` 相关章节 |
| 改采集生命周期、worker 或 pending 轮询 | `docs/采集任务生命周期说明.md` |
| 改平台端展示、metadata 或原型页面口径 | `docs/原型功能_API映射整合精简版.md` 相关平台端/信源章节 |
| 改配置或部署 | `.env.example`、README、部署说明相关章节 |
| 查当前 Aidso 实现背景 | `backend/app/geo_monitoring/adapters/aidso.py`、`services/collection.py`、`services/platforms.py`、`schemas.py`、`models.py` |

## 用户推荐指令格式

```text
执行 Task M5：Molizhishu Client / Adapter
```

或完整格式：

```text
执行 docs/Cursor模力指数API替换Aidso开发任务书.md 的 Task M5：Molizhishu Client / Adapter。
```

Agent 应自动读取本索引、定位任务书局部章节、按 Superpowers 工作流执行测试先行、实现、验收和文档同步，无需用户重复粘贴任务书内容。
