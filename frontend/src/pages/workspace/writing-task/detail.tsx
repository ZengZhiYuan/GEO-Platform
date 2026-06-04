import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Col,
  Descriptions,
  Popconfirm,
  Row,
  Space,
  Spin,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { ArrowLeftOutlined, ReloadOutlined } from '@ant-design/icons'

import {
  cancelWritingTask,
  getWritingTask,
  retryWritingTask,
} from '@/api/writingTask'
import { listArticles } from '@/api/article'
import { listContentCategories } from '@/api/contentCategory'
import { listImageCategories } from '@/api/imageCategory'
import { listBrandKnowledges } from '@/api/brandKnowledge'
import { listWritingRules } from '@/api/writingRule'
import type {
  ArticleItem,
  ArticleStatus,
  TaskStatus,
  WritingTaskItem,
} from '@/types/workspace'
import {
  ArticleStatusColorMap,
  TaskStatusColorMap,
  getArticleStatusLabel,
  getTaskStatusLabel,
} from '@/utils/enums'
import { formatDateTime } from '@/utils/format'

const { Title, Text } = Typography

const LIST_PATH = '/workspace/writing-tasks'
const POLL_INTERVAL = 3000
/** 处于这些状态时轮询刷新进度。 */
const POLLING_STATUS: TaskStatus[] = ['pending', 'running']

/** id -> 名称 映射，用于素材配置展示可读名称。 */
type NameMap = Record<number, string>

/** 写作任务详情页（/workspace/writing-tasks/:id）。 */
export default function WritingTaskDetailPage() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const numericId = Number(id)
  const validId = Number.isInteger(numericId) && numericId > 0

  const [task, setTask] = useState<WritingTaskItem | null>(null)
  const [articles, setArticles] = useState<ArticleItem[]>([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [acting, setActing] = useState(false)

  // 素材名称映射（一次性加载，轮询不重复拉取）
  const [nameMaps, setNameMaps] = useState<{
    category: NameMap
    image: NameMap
    brand: NameMap
    rule: NameMap
  }>({ category: {}, image: {}, brand: {}, rule: {} })

  // 轮询用：始终读取最新任务状态，避免重建定时器
  const taskStatusRef = useRef<TaskStatus | undefined>(undefined)

  /** 拉取任务详情 + 小任务列表。silent=true 时用于轮询，不触发整页 loading。 */
  const fetchDetail = useCallback(
    async (silent = false) => {
      if (!validId) return
      if (!silent) {
        setLoading(true)
        setLoadError(false)
      }
      try {
        const [taskData, articleData] = await Promise.all([
          getWritingTask(numericId),
          listArticles({ writing_task_id: numericId, page: 1, page_size: 200 }),
        ])
        setTask(taskData)
        taskStatusRef.current = taskData.task_status
        setArticles(articleData.items)
      } catch {
        // 错误提示已由 axios 拦截器统一弹出
        if (!silent) setLoadError(true)
      } finally {
        if (!silent) setLoading(false)
      }
    },
    [validId, numericId],
  )

  /** 一次性加载素材名称映射，用于把外键 ID 显示为可读名称。 */
  const fetchNameMaps = useCallback(async () => {
    try {
      const [categories, images, brands, rules] = await Promise.all([
        listContentCategories({ page: 1, page_size: 200 }),
        listImageCategories({ page: 1, page_size: 200 }),
        listBrandKnowledges({ page: 1, page_size: 200 }),
        listWritingRules({ page: 1, page_size: 200 }),
      ])
      const toMap = <T,>(items: T[], getName: (i: T) => string, getId: (i: T) => number) =>
        items.reduce<NameMap>((acc, i) => {
          acc[getId(i)] = getName(i)
          return acc
        }, {})
      setNameMaps({
        category: toMap(categories.items, (i) => i.group_name, (i) => i.id),
        image: toMap(images.items, (i) => i.category_name, (i) => i.id),
        brand: toMap(brands.items, (i) => i.knowledge_name, (i) => i.id),
        rule: toMap(rules.items, (i) => i.rule_name, (i) => i.id),
      })
    } catch {
      // 名称映射失败不阻断详情展示，回退显示 ID
    }
  }, [])

  useEffect(() => {
    fetchDetail()
    fetchNameMaps()
  }, [fetchDetail, fetchNameMaps])

  // 轮询：任务处于 pending/running 时每 3 秒刷新
  useEffect(() => {
    if (!validId) return
    const timer = window.setInterval(() => {
      if (taskStatusRef.current && POLLING_STATUS.includes(taskStatusRef.current)) {
        fetchDetail(true)
      }
    }, POLL_INTERVAL)
    return () => window.clearInterval(timer)
  }, [validId, fetchDetail])

  const handleCancel = async () => {
    if (!task) return
    setActing(true)
    try {
      await cancelWritingTask(task.id)
      message.success('任务已取消')
      fetchDetail()
    } catch {
      // 失败提示已由拦截器弹出
    } finally {
      setActing(false)
    }
  }

  const handleRetry = async () => {
    if (!task) return
    setActing(true)
    try {
      await retryWritingTask(task.id)
      message.success('已重新提交失败任务')
      fetchDetail()
    } catch {
      // 失败提示已由拦截器弹出
    } finally {
      setActing(false)
    }
  }

  // 生成进度统计（由小任务列表派生）
  const stats = {
    total: articles.length,
    generating: articles.filter((a) => a.status === 'generating').length,
    pending_review: articles.filter((a) => a.status === 'pending_review').length,
    normal: articles.filter((a) => a.status === 'normal').length,
    disabled: articles.filter((a) => a.status === 'disabled').length,
    failed: articles.filter((a) => a.status === 'failed').length,
  }

  const canCancel =
    task != null && POLLING_STATUS.includes(task.task_status)
  const canRetry =
    task != null &&
    (task.task_status === 'failed' || stats.failed > 0) &&
    task.task_status !== 'cancelled'

  const articleColumns: ColumnsType<ArticleItem> = [
    {
      title: '文章标题',
      dataIndex: 'article_title',
      key: 'article_title',
      ellipsis: true,
      render: (value: string | null, record) => {
        const title = value || '（待生成）'
        // 点击标题进入文章编辑页（编辑页由后续任务实现）
        return (
          <Button
            type="link"
            size="small"
            style={{ padding: 0 }}
            onClick={() => navigate(`/workspace/articles/${record.id}/edit`)}
          >
            {title}
          </Button>
        )
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (value: ArticleStatus) => (
        <Tag color={ArticleStatusColorMap[value] ?? 'default'}>
          {getArticleStatusLabel(value)}
        </Tag>
      ),
    },
    {
      title: '错误信息',
      dataIndex: 'error_message',
      key: 'error_message',
      ellipsis: true,
      render: (value: string | null) =>
        value ? <Text type="danger">{value}</Text> : '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 200,
      render: (value: string) => formatDateTime(value),
    },
  ]

  if (!validId) {
    return (
      <div>
        <Title level={4} style={{ marginTop: 0 }}>
          写作任务详情
        </Title>
        <Alert
          type="error"
          showIcon
          message="无效的任务 ID"
          description="请从写作任务列表进入详情页。"
          action={
            <Button size="small" onClick={() => navigate(LIST_PATH)}>
              返回列表
            </Button>
          }
        />
      </div>
    )
  }

  const nameOrId = (map: NameMap, value?: number | null) =>
    value == null ? '-' : map[value] ?? `#${value}`

  return (
    <div>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(LIST_PATH)}>
            返回
          </Button>
          <Title level={4} style={{ margin: 0 }}>
            写作任务详情
          </Title>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => fetchDetail()}>
            刷新
          </Button>
          {canCancel && (
            <Popconfirm
              title="取消任务"
              description="确定取消该任务吗？未开始的小任务将被取消。"
              okText="确定"
              okButtonProps={{ danger: true }}
              cancelText="再想想"
              onConfirm={handleCancel}
            >
              <Button danger loading={acting}>
                取消任务
              </Button>
            </Popconfirm>
          )}
          {canRetry && (
            <Button type="primary" loading={acting} onClick={handleRetry}>
              重试失败项
            </Button>
          )}
        </Space>
      </Space>

      {loadError && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="详情加载失败"
          description="请检查网络或后端服务后重试。"
          action={
            <Button size="small" danger onClick={() => fetchDetail()}>
              重试
            </Button>
          }
        />
      )}

      <Spin spinning={loading}>
        {/* 任务基础信息 */}
        <Card title="任务基础信息" style={{ marginBottom: 16 }}>
          <Descriptions column={{ xs: 1, sm: 2 }} size="small">
            <Descriptions.Item label="任务名称">
              {task?.task_name ?? '-'}
            </Descriptions.Item>
            <Descriptions.Item label="任务状态">
              {task ? (
                <Tag color={TaskStatusColorMap[task.task_status] ?? 'default'}>
                  {getTaskStatusLabel(task.task_status)}
                </Tag>
              ) : (
                '-'
              )}
            </Descriptions.Item>
            <Descriptions.Item label="蒸馏训练词">
              {task?.distill_keywords ?? '-'}
            </Descriptions.Item>
            <Descriptions.Item label="AI 创作数量">
              {task?.ai_generate_count ?? '-'}
            </Descriptions.Item>
            <Descriptions.Item label="文章结果状态">
              {task?.article_result_status || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {formatDateTime(task?.created_at)}
            </Descriptions.Item>
            <Descriptions.Item label="更新时间">
              {formatDateTime(task?.updated_at)}
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* 任务素材配置 */}
        <Card title="任务素材配置" style={{ marginBottom: 16 }}>
          <Descriptions column={{ xs: 1, sm: 2 }} size="small">
            <Descriptions.Item label="文章分类">
              {nameOrId(nameMaps.category, task?.content_category_id)}
            </Descriptions.Item>
            <Descriptions.Item label="画像图库">
              {nameOrId(nameMaps.image, task?.image_category_id)}
            </Descriptions.Item>
            <Descriptions.Item label="文章配图数量">
              {task?.article_image_count ?? '-'}
            </Descriptions.Item>
            <Descriptions.Item label="企业知识库">
              {nameOrId(nameMaps.brand, task?.brand_knowledge_id)}
            </Descriptions.Item>
            <Descriptions.Item label="内容创作指令">
              {nameOrId(nameMaps.rule, task?.content_rule_id)}
            </Descriptions.Item>
            <Descriptions.Item label="标题创作指令">
              {nameOrId(nameMaps.rule, task?.title_rule_id)}
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* 生成进度 */}
        <Card title="生成进度" style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col xs={12} sm={8} md={4}>
              <Statistic title="总数量" value={stats.total} />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Statistic title="生成中" value={stats.generating} />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Statistic title="待审核" value={stats.pending_review} />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Statistic
                title="正常"
                value={stats.normal}
                valueStyle={{ color: '#52c41a' }}
              />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Statistic title="禁用" value={stats.disabled} />
            </Col>
            <Col xs={12} sm={8} md={4}>
              <Statistic
                title="失败"
                value={stats.failed}
                valueStyle={{ color: stats.failed > 0 ? '#ff4d4f' : undefined }}
              />
            </Col>
          </Row>
        </Card>

        {/* 小任务文章列表 */}
        <Card title="小任务文章列表">
          <Table<ArticleItem>
            rowKey="id"
            columns={articleColumns}
            dataSource={articles}
            pagination={false}
            scroll={{ x: 720 }}
          />
        </Card>
      </Spin>
    </div>
  )
}
