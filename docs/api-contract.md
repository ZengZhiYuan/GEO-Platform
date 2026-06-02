# API 接口契约

## 通用规范

Base URL:

```txt
/api
```

统一响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

分页响应：

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

## 模块接口命名规范

### 关键词库

- `GET /api/keywords`
- `POST /api/keywords`
- `GET /api/keywords/{id}`
- `PUT /api/keywords/{id}`
- `DELETE /api/keywords/{id}`

### 标题灵感

- `GET /api/title-inspirations`
- `POST /api/title-inspirations`
- `GET /api/title-inspirations/{id}`
- `PUT /api/title-inspirations/{id}`
- `DELETE /api/title-inspirations/{id}`

### 画像图库分类

- `GET /api/image-categories`
- `POST /api/image-categories`
- `GET /api/image-categories/{id}`
- `PUT /api/image-categories/{id}`
- `DELETE /api/image-categories/{id}`

### 图片详情

- `GET /api/image-assets`
- `POST /api/image-assets`
- `GET /api/image-assets/{id}`
- `PUT /api/image-assets/{id}`
- `DELETE /api/image-assets/{id}`

### 品牌知识库

- `GET /api/brand-knowledges`
- `POST /api/brand-knowledges`
- `GET /api/brand-knowledges/{id}`
- `PUT /api/brand-knowledges/{id}`
- `DELETE /api/brand-knowledges/{id}`

### 写作规范

- `GET /api/writing-rules`
- `POST /api/writing-rules`
- `GET /api/writing-rules/{id}`
- `PUT /api/writing-rules/{id}`
- `DELETE /api/writing-rules/{id}`

### 内容分类

- `GET /api/content-categories`
- `POST /api/content-categories`
- `GET /api/content-categories/{id}`
- `PUT /api/content-categories/{id}`
- `DELETE /api/content-categories/{id}`

### 写作任务

- `GET /api/writing-tasks`
- `POST /api/writing-tasks`
- `GET /api/writing-tasks/{id}`
- `POST /api/writing-tasks/{id}/cancel`
- `POST /api/writing-tasks/{id}/retry`

### 文章清单

- `GET /api/articles`
- `GET /api/articles/{id}`
- `PUT /api/articles/{id}`
- `POST /api/articles/{id}/status`
````
