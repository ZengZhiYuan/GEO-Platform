# CLAUDE.md

## 项目名称

实朴GEO

## 项目定位

实朴GEO 是一个面向小红书、知乎、微信公众号等自媒体平台的内容生成 Web 应用。系统初始版本包含两个一级模块：

1. 素材中心
2. 写作工作台

核心业务闭环为：

关键词库 → 标题灵感 → 画像图库 → 品牌知识库 → 写作规范 → 写作任务 → MQ异步生成 → 文章清单 → 人工审核/编辑

## 开发总原则

1. 严格阅读并遵守 `docs/claude-code-dev.md`。
2. 不允许一次性实现全部功能。
3. 每次开发只处理一个明确阶段。
4. 前后端分离开发。
5. 接口优先，前后端通过接口契约协作。
6. 后端优先保证数据模型、接口、异步任务状态流转正确。
7. 前端优先保证页面路由、列表页、表单页、详情页、状态展示和操作闭环正确。
8. 所有新增功能必须包含必要的错误处理。
9. 每完成一个阶段，必须更新 `docs/progress.md`。
10. 每次修改代码前，先检查项目结构和已有实现，避免重复造文件、重复造模块。

## 技术栈约定

### 后端

* Python
* FastAPI
* SQLAlchemy
* Alembic
* PostgreSQL
* Redis
* Celery 或 Dramatiq
* Pydantic
* Uvicorn

### 前端

* React
* TypeScript
* Vite
* Ant Design
* React Router
* Axios
* Zustand 或 Redux Toolkit

## 后端模块边界

后端按业务域拆分：

1. keyword：关键词库
2. title_inspiration：标题灵感
3. image_library：画像图库
4. brand_knowledge：品牌知识库
5. writing_rule：写作规范
6. content_category：内容分类
7. writing_task：写作任务
8. article：文章清单
9. ai_generation：AI内容生成服务
10. common：统一响应、分页、异常、权限、配置

## 前端模块边界

前端按页面模块拆分：

1. 素材中心 / 关键词库
2. 素材中心 / 标题灵感
3. 素材中心 / 画像图库
4. 素材中心 / 品牌知识库
5. 写作工作台 / 写作规范
6. 写作工作台 / 内容分类
7. 写作工作台 / 写作任务
8. 写作工作台 / 文章清单

## 页面开发规则

每个管理页面至少包含：

1. 列表页
2. 新增弹窗或新增页
3. 编辑弹窗或编辑页
4. 删除确认
5. 搜索筛选
6. 分页
7. 状态展示
8. 空数据状态
9. 加载状态
10. 错误提示

## 接口开发规则

所有接口统一返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

分页接口统一返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 10
  }
}
```

## 异步任务规则

写作任务创建后，不直接同步生成所有文章，而是：

1. 创建大任务 writing_task
2. 根据 AI创作数量 创建多个 article 小任务
3. 将小任务 ID 投递到 MQ
4. Worker 消费小任务
5. 调用 AI 生成标题、正文、封面图
6. 更新小任务状态
7. 所有小任务完成后，更新大任务状态

## 状态流转

### 大任务状态

* draft：草稿
* pending：等待执行
* running：执行中
* completed：已完成
* failed：执行失败
* cancelled：已取消

### 小任务/文章状态

* generating：生成中
* pending_review：待审核
* normal：正常
* disabled：禁用
* failed：生成失败

## 开发流程

每次开始新任务时：

1. 读取 `CLAUDE.md`
2. 读取 `docs/claude-code-dev.md`
3. 读取 `docs/progress.md`
4. 检查当前代码结构
5. 明确本次任务范围
6. 制定执行计划
7. 开始编码
8. 运行测试或启动验证
9. 更新 `docs/progress.md`
10. 总结本次变更和下一步建议

## 禁止事项

1. 不要删除已有业务代码，除非明确说明原因。
2. 不要随意改变接口字段名称。
3. 不要绕过接口契约直接临时写死数据。
4. 不要一次性生成大量不可验证代码。
5. 不要把前端、后端、数据库、MQ 全部混在一个任务里完成。
6. 不要忽略启动命令、测试命令和错误日志。
7. 不要只说完成，必须说明修改了哪些文件、如何验证。
