# Aidso Collection Source Design

## Goal

在现有 AI 应用监测后端中新增第二种数据采集方式：通过 Aidso 第三方 API 获取 AI Web 端和 App 端真实回答结果，同时尽量复用现有答案落库、引用解析、品牌匹配、分析、看板和报告逻辑。

## Confirmed Product Choice

创建监测运行时新增 `collection_source` 入参：

- `official`：默认值，保持当前调用 AI 厂商官方 API 的行为。
- `aidso`：通过 Aidso OpenAPI 采集各 AI 平台 Web/App 端结果。

当 `collection_source="aidso"` 时，用户可在创建运行入参中控制 Aidso 深度思考：

- `aidso_thinking_enabled`：布尔值，默认 `true`。提交 Aidso API 时转换为 `thinkingEnabled: 1` 或 `thinkingEnabled: 0`。

`platform_codes` 继续表达本次运行的展示与分析维度。Aidso 数据源使用独立的平台编码表示端侧，例如：

- `aidso_doubao_web` -> Aidso 平台名 `DB`，豆包 Web 端。
- `aidso_doubao_app` -> Aidso 平台名 `DOUBA`，豆包 App 端。
- `aidso_deepseek_web` -> Aidso 平台名 `DP`，DeepSeek Web 端。
- `aidso_deepseek_app` -> Aidso 平台名 `DPA`，DeepSeek App 端。
- `aidso_kimi_web` -> Aidso 平台名 `KIMI`，Kimi Web 端。
- `aidso_yuanbao_web` -> Aidso 平台名 `TXYB`，元宝 Web 端。
- `aidso_yuanbao_app` -> Aidso 平台名 `TXYBA`，元宝 App 端。
- `aidso_qwen_web` -> Aidso 平台名 `TYQW`，千问 Web 端。
- `aidso_qwen_app` -> Aidso 平台名 `TYQWA`，千问 App 端。
- `aidso_baidu_web` -> Aidso 平台名 `BDAI`，百度 AI。
- `aidso_douyin_web` -> Aidso 平台名 `DYAI`，抖音 AI。
- `aidso_wenxin_web` -> Aidso 平台名 `WXYY`，文心一言。

## Architecture

保留现有采集服务的核心契约：每个 QueryTask 最终产出一个 `PlatformAnswer`。Aidso 作为新的采集数据源接入到适配器层，负责把 Aidso 的提交/轮询响应转换为 `PlatformAnswer`。

主要边界：

- API 层：`RunCreate` 增加 `collection_source`，默认 `official`，不破坏旧请求。
- 数据层：`geo_monitor_run` 增加 `collection_source` 字段，用于每次运行记录实际采集方式。
- 平台配置：`geo_ai_platform` 增加 Aidso 端侧平台种子数据，仍使用现有 `platform_code` 作为展示、筛选和分析维度。
- 采集层：运行时根据 `collection_source` 与 `platform_code` 选择官方适配器或 Aidso 适配器。
- 分析层：继续按 `platform_code` 聚合；Aidso Web/App 平台自然分开展示。

## Aidso API Mapping

Aidso 文档中的服务地址为 `https://odapi.aidso.com`，需要从环境变量读取 token。

提交任务：

- `POST /open/mt/task_commit`
- Header: `Authorization: <token>`
- Body:

```json
{
  "prompt": "问题文本",
  "platform": [
    {
      "name": "DB",
      "thinkingEnabled": 1
    }
  ]
}
```

获取结果：

- `GET /open/mt/get_result?reqId=<reqId>`
- Header: `Authorization: <token>`
- `data.status = ING` 表示仍在生成。
- `data.status = SUCCESS` 表示可读取结果。

结果字段转换：

- `result[].context` -> `PlatformAnswer.text`
- `result[].quote` -> `PlatformAnswer.citations`
- `data.taskId` 或 `reqId` -> `PlatformAnswer.provider_request_id`
- 完整 Aidso 响应 -> `raw_response`
- Aidso 无 token 用量字段，`usage` 固定为空字典，由现有落库逻辑写为 0。
- `model` 写为 Aidso 平台编码对应的展示模型名，例如 `aidso:DB`。

`quote` 在示例中是 JSON 字符串，适配器需要安全解析；解析失败时不影响正文落库，但引用列表为空，并保留原始响应用于排查。

## Runtime Behavior

`collection_source="official"`：

- `platform_codes` 只能使用当前官方平台编码，如 `doubao`、`qwen`、`yuanbao`、`deepseek`、`kimi`。
- 使用现有官方适配器和密钥池逻辑。

`collection_source="aidso"`：

- `platform_codes` 使用 Aidso 端侧平台编码。
- 每个 QueryTask 独立提交一个 Aidso 任务，提交时只包含该任务对应的一个 Aidso 平台。
- 首次执行时提交 Aidso 任务，并将返回的 `reqId`、`taskId`、Aidso 平台名和 `thinkingEnabled` 写入现有 `QueryTask.request_json`。
- 后续重试时若 `QueryTask.request_json` 已有 Aidso `reqId`，不再重复提交，直接轮询该 `reqId`。
- 如果结果仍为 `ING`，抛出可重试的 `AdapterError`，让现有 QueryTask 重试机制继续排队。
- Aidso 任务最迟可能 24 小时才完成，因此 Aidso 平台的 `max_attempts` 应通过平台配置或环境默认值设置得比官方平台更高。首版不引入单独的长期轮询表，先复用现有重试机制。

## Configuration

新增环境变量：

- `AIDSO_ENABLED=false`
- `AIDSO_BASE_URL=https://odapi.aidso.com`
- `AIDSO_API_TOKEN=`

运行时校验：

- 当 `AIDSO_ENABLED=true` 时，必须提供 `AIDSO_API_TOKEN`。
- Aidso token 不写入数据库、不写入日志、不出现在错误消息中。
- Aidso `thinkingEnabled` 不从环境变量读取，由创建运行入参 `aidso_thinking_enabled` 控制。

## Error Handling

Aidso HTTP 错误沿用现有分类：

- `401` / `403` -> `UNAUTHORIZED`
- `429` -> `RATE_LIMITED`
- `5xx` -> `SERVER_ERROR`
- 网络超时或连接失败 -> `NETWORK_ERROR`
- Aidso `code != 200` -> 根据消息和状态码映射为 `INVALID_REQUEST` 或 `UNKNOWN`

Aidso 业务状态：

- `data.status = ING` -> `NETWORK_ERROR`，可重试。
- `data.status = SUCCESS` 且无非空 `context` -> `INVALID_REQUEST`。
- 缺少 `reqId` 或 Aidso 平台映射不存在 -> `INVALID_REQUEST`。

## Testing

测试必须先行，覆盖：

- `RunCreate` 默认 `collection_source="official"`，旧请求不变。
- `RunCreate` 支持 `aidso_thinking_enabled`，并在 Aidso 提交请求中映射为 `thinkingEnabled`。
- 创建 Aidso 运行时，`collection_source` 持久化到 run，`platform_codes` 使用 Aidso 端侧编码。
- Aidso 首次提交后会把 `reqId/taskId` 写入 `QueryTask.request_json`，重试时复用已有 `reqId`。
- Aidso 适配器提交请求体、Authorization 头、平台名映射正确。
- Aidso `SUCCESS` 响应能解析 `context` 和 quote JSON 字符串。
- Aidso `ING` 映射为可重试错误。
- Aidso HTTP/业务错误不会泄露 token。
- 采集服务在 Aidso 任务成功后仍走现有答案、引用、品牌结果落库逻辑。

## Documentation

需要更新：

- `docs/API接口文档.md`：`POST /runs` 增加 `collection_source`，平台章节列出 Aidso 端侧编码。
- `.env.example`：增加 Aidso 配置项。
- README 或操作手册中补充 Aidso 数据源使用示例。

## Out Of Scope

首版不实现：

- 单次 Aidso `task_commit` 批量提交多个平台后跨 QueryTask 共享 `taskId`。
- 独立 Aidso 轮询状态表。
- 前端页面改版。
- 对 `think`、`suggestions`、`rich_media_block` 的结构化展示。
- 对 App 商品卡标识的独立解析与指标化。
