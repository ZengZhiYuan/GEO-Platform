# 实朴GEO API接口契约

## 通用规范

Base URL:

```txt
/api
````

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

---

## 关键词库

* GET /api/keywords
* POST /api/keywords
* GET /api/keywords/{id}
* PUT /api/keywords/{id}
* DELETE /api/keywords/{id}

字段：

* id
* main_word
* question_count
* optimize_status
* created_at
* updated_at

---

## 标题灵感

* GET /api/title-inspirations
* POST /api/title-inspirations
* GET /api/title-inspirations/{id}
* PUT /api/title-inspirations/{id}
* DELETE /api/title-inspirations/{id}

字段：

* id
* main_word
* question
* collect_status
* created_at
* updated_at

---

## 画像图库分类

* GET /api/image-categories
* POST /api/image-categories
* GET /api/image-categories/{id}
* PUT /api/image-categories/{id}
* DELETE /api/image-categories/{id}

字段：

* id
* category_name
* image_count
* created_at
* updated_at

---

## 图片详情

* GET /api/image-assets
* POST /api/image-assets
* GET /api/image-assets/{id}
* PUT /api/image-assets/{id}
* DELETE /api/image-assets/{id}

字段：

* id
* category_id
* image_url
* use_count
* created_at
* updated_at

---

## 品牌知识库

* GET /api/brand-knowledges
* POST /api/brand-knowledges
* GET /api/brand-knowledges/{id}
* PUT /api/brand-knowledges/{id}
* DELETE /api/brand-knowledges/{id}

字段：

* id
* knowledge_name
* company_name
* company_short_name
* creation_direction
* copywriting_type
* product_service
* product_features
* created_at
* updated_at

---

## 写作规范

* GET /api/writing-rules
* POST /api/writing-rules
* GET /api/writing-rules/{id}
* PUT /api/writing-rules/{id}
* DELETE /api/writing-rules/{id}

字段：

* id
* rule_name
* creation_type
* instruction_content
* created_at
* updated_at

creation_type 枚举：

* article_creation
* title_creation
* traffic_replication

---

## 内容分类

* GET /api/content-categories
* POST /api/content-categories
* GET /api/content-categories/{id}
* PUT /api/content-categories/{id}
* DELETE /api/content-categories/{id}

字段：

* id
* group_name
* article_count
* created_at
* updated_at

---

## 写作任务

* GET /api/writing-tasks
* POST /api/writing-tasks
* GET /api/writing-tasks/{id}
* POST /api/writing-tasks/{id}/cancel
* POST /api/writing-tasks/{id}/retry

字段：

* id
* task_name
* content_category_id
* distill_keywords
* image_category_id
* article_image_count
* brand_knowledge_id
* content_rule_id
* title_rule_id
* article_result_status
* ai_generate_count
* task_status
* created_at
* updated_at

task_status 枚举：

* draft
* pending
* running
* completed
* failed
* cancelled

---

## 文章清单

* GET /api/articles
* GET /api/articles/{id}
* PUT /api/articles/{id}
* POST /api/articles/{id}/status

字段：

* id
* writing_task_id
* article_title
* cover_image_url
* status
* content
* error_message
* created_at
* updated_at

status 枚举：

* generating
* pending_review
* normal
* disabled
* failed