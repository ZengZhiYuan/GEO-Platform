# 前端页面与跳转设计

## 一级菜单

### 素材中心

- `/material/keywords`
- `/material/title-inspirations`
- `/material/image-library`
- `/material/brand-knowledge`

### 写作工作台

- `/workspace/writing-rules`
- `/workspace/content-categories`
- `/workspace/writing-tasks`
- `/workspace/articles`

## 页面跳转关系

### 关键词库

关键词库列表页：

```txt
/material/keywords
```

操作：

- 新增关键词：打开弹窗
- 编辑关键词：打开弹窗
- 删除关键词：二次确认
- 查看标题灵感：跳转到 `/material/title-inspirations?keyword=xxx`

### 标题灵感

标题灵感列表页：

```txt
/material/title-inspirations
```

操作：

- 支持根据主词筛选
- 支持收录状态筛选
- 新增问题：打开弹窗
- 编辑问题：打开弹窗

### 画像图库

图库分类页：

```txt
/material/image-library
```

图片详情页：

```txt
/material/image-library/:categoryId
```

操作：

- 点击图库分类进入图片详情
- 图片详情支持图片预览、复制 URL、删除

### 品牌知识库

品牌知识库列表：

```txt
/material/brand-knowledge
```

编辑页：

```txt
/material/brand-knowledge/:id/edit
```

### 写作规范

写作规范列表：

```txt
/workspace/writing-rules
```

操作：

- 新增指令
- 编辑指令
- 按创作类型筛选

### 内容分类

内容分类列表：

```txt
/workspace/content-categories
```

### 写作任务

写作任务列表：

```txt
/workspace/writing-tasks
```

新建任务页：

```txt
/workspace/writing-tasks/create
```

任务详情页：

```txt
/workspace/writing-tasks/:id
```

操作：

- 新建任务成功后跳转任务详情
- 任务详情展示大任务信息和小任务列表
- 点击小任务进入文章编辑页

### 文章清单

文章列表：

```txt
/workspace/articles
```

文章编辑页：

```txt
/workspace/articles/:id/edit
```

操作：

- 编辑文章标题
- 编辑正文内容
- 修改封面图
- 切换状态：待审核、正常、禁用