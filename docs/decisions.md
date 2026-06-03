# 技术决策记录

## 001：前端使用 React + Vite + TypeScript + Ant Design

原因：

- 管理后台开发速度快
- 表格、表单、弹窗组件完整
- TypeScript 便于维护接口类型

## 002：后端使用 FastAPI

原因：

- Python AI 生态兼容性好
- 接口开发快
- Swagger 自动生成

## 003：异步任务使用 Redis + Celery 或 Dramatiq

原因：

- 简单成熟
- 适合后台文章生成任务
- 后续可扩展失败重试和任务监控

## 004：AI生成服务第一版使用 Mock 实现

原因：

- 先跑通业务闭环
- 避免早期被模型接口、费用、网络、提示词问题阻塞