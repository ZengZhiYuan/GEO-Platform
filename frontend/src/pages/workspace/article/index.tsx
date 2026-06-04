import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Button,
  Dropdown,
  Form,
  Image,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { MenuProps } from 'antd'
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons'

import { listArticles, updateArticleStatus } from '@/api/article'
import type {
  ArticleEditableStatus,
  ArticleItem,
  ArticleStatus,
} from '@/types/workspace'
import {
  ArticleEditableStatusOptions,
  ArticleStatusColorMap,
  ArticleStatusOptions,
  getArticleStatusLabel,
} from '@/utils/enums'
import { formatDateTime } from '@/utils/format'

const { Title } = Typography

interface SearchFormValues {
  article_title?: string
  status?: ArticleStatus
}

/** 文章清单列表页（/workspace/articles）。 */
export default function ArticleListPage() {
  const navigate = useNavigate()
  const [searchForm] = Form.useForm<SearchFormValues>()

  // 列表数据与状态
  const [items, setItems] = useState<ArticleItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)

  // 分页 + 已提交的筛选条件
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [articleTitle, setArticleTitle] = useState('')
  const [status, setStatus] = useState<ArticleStatus | undefined>(undefined)

  // 行内状态切换 loading（按文章 id 标记）
  const [statusUpdatingId, setStatusUpdatingId] = useState<number | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setLoadError(false)
    try {
      const data = await listArticles({
        page,
        page_size: pageSize,
        article_title: articleTitle || undefined,
        status,
      })
      setItems(data.items)
      setTotal(data.total)
    } catch {
      // 错误提示已由 axios 拦截器统一弹出，这里仅标记错误态用于页面展示
      setLoadError(true)
      setItems([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, articleTitle, status])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleSearch = () => {
    const values = searchForm.getFieldsValue()
    setPage(1)
    setArticleTitle((values.article_title || '').trim())
    setStatus(values.status)
  }

  const handleReset = () => {
    searchForm.resetFields()
    setPage(1)
    setArticleTitle('')
    setStatus(undefined)
  }

  const handleChangeStatus = async (
    record: ArticleItem,
    nextStatus: ArticleEditableStatus,
  ) => {
    if (record.status === nextStatus) return
    setStatusUpdatingId(record.id)
    try {
      await updateArticleStatus(record.id, { status: nextStatus })
      message.success('状态更新成功')
      fetchData()
    } catch {
      // 失败提示已由拦截器弹出
    } finally {
      setStatusUpdatingId(null)
    }
  }

  const columns: ColumnsType<ArticleItem> = [
    {
      title: '封面',
      dataIndex: 'cover_image_url',
      key: 'cover_image_url',
      width: 88,
      render: (value: string | null) =>
        value ? (
          <Image
            src={value}
            alt="封面"
            width={56}
            height={56}
            style={{ objectFit: 'cover', borderRadius: 4 }}
          />
        ) : (
          <span style={{ color: '#bfbfbf' }}>无</span>
        ),
    },
    {
      title: '文章标题',
      dataIndex: 'article_title',
      key: 'article_title',
      ellipsis: true,
      render: (value: string, record) => (
        <Button
          type="link"
          style={{ padding: 0, height: 'auto', textAlign: 'left' }}
          onClick={() => navigate(`/workspace/articles/${record.id}/edit`)}
        >
          {value || '（未命名）'}
        </Button>
      ),
    },
    {
      title: '所属任务',
      dataIndex: 'writing_task_id',
      key: 'writing_task_id',
      width: 110,
      render: (value: number) => (value ? `#${value}` : '-'),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (value: ArticleStatus) => (
        <Tag color={ArticleStatusColorMap[value] ?? 'default'}>
          {getArticleStatusLabel(value)}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 190,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      fixed: 'right',
      render: (_, record) => {
        const statusMenu: MenuProps = {
          items: ArticleEditableStatusOptions.map((opt) => ({
            key: opt.value,
            label: opt.label,
            disabled: record.status === opt.value,
          })),
          onClick: ({ key }) =>
            handleChangeStatus(record, key as ArticleEditableStatus),
        }
        return (
          <Space size="middle">
            <Button
              type="link"
              size="small"
              onClick={() => navigate(`/workspace/articles/${record.id}/edit`)}
            >
              编辑
            </Button>
            <Dropdown
              menu={statusMenu}
              trigger={['click']}
              disabled={statusUpdatingId === record.id}
            >
              <Button
                type="link"
                size="small"
                loading={statusUpdatingId === record.id}
              >
                状态切换
              </Button>
            </Dropdown>
          </Space>
        )
      },
    },
  ]

  return (
    <div>
      <Title level={4} style={{ marginTop: 0 }}>
        文章清单
      </Title>

      {/* 搜索 / 筛选区 */}
      <Form
        form={searchForm}
        layout="inline"
        style={{ marginBottom: 16, rowGap: 12 }}
        onFinish={handleSearch}
      >
        <Form.Item name="article_title" label="文章标题">
          <Input
            placeholder="按标题搜索"
            allowClear
            style={{ width: 220 }}
            onPressEnter={handleSearch}
          />
        </Form.Item>
        <Form.Item name="status" label="状态">
          <Select
            placeholder="全部状态"
            allowClear
            style={{ width: 160 }}
            options={ArticleStatusOptions}
          />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
              查询
            </Button>
            <Button icon={<ReloadOutlined />} onClick={handleReset}>
              重置
            </Button>
          </Space>
        </Form.Item>
      </Form>

      {/* 错误提示 */}
      {loadError && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="数据加载失败"
          description="请检查网络或后端服务后重试。"
          action={
            <Button size="small" danger onClick={fetchData}>
              重试
            </Button>
          }
        />
      )}

      {/* 表格 + 分页 */}
      <Table<ArticleItem>
        rowKey="id"
        columns={columns}
        dataSource={items}
        loading={loading}
        scroll={{ x: 900 }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (nextPage, nextPageSize) => {
            setPage(nextPage)
            setPageSize(nextPageSize)
          },
        }}
      />
    </div>
  )
}
