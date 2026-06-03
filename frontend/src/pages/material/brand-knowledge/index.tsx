import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Form,
  Input,
  Popconfirm,
  Space,
  Table,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'

import {
  createBrandKnowledge,
  deleteBrandKnowledge,
  listBrandKnowledges,
} from '@/api/brandKnowledge'
import type {
  BrandKnowledgeCreatePayload,
  BrandKnowledgeItem,
} from '@/types/material'
import { formatDateTime } from '@/utils/format'
import BrandKnowledgeFormDrawer from './BrandKnowledgeFormDrawer'

const { Title, Paragraph } = Typography

interface SearchFormValues {
  knowledge_name?: string
  company_name?: string
}

/** 展示长文本：空值兜底为 `-`。 */
function renderText(value?: string | null) {
  const text = (value ?? '').trim()
  if (!text) return '-'
  return (
    <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>{text}</Paragraph>
  )
}

/** 品牌知识库列表页（/material/brand-knowledge）。 */
export default function BrandKnowledgePage() {
  const navigate = useNavigate()
  const [searchForm] = Form.useForm<SearchFormValues>()

  // 列表数据与状态
  const [items, setItems] = useState<BrandKnowledgeItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)

  // 分页 + 已提交的筛选条件
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [knowledgeName, setKnowledgeName] = useState('')
  const [companyName, setCompanyName] = useState('')

  // 新增 Drawer
  const [createOpen, setCreateOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // 详情 Drawer
  const [detailRecord, setDetailRecord] = useState<BrandKnowledgeItem | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setLoadError(false)
    try {
      const data = await listBrandKnowledges({
        page,
        page_size: pageSize,
        knowledge_name: knowledgeName || undefined,
        company_name: companyName || undefined,
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
  }, [page, pageSize, knowledgeName, companyName])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleSearch = () => {
    const values = searchForm.getFieldsValue()
    setPage(1)
    setKnowledgeName((values.knowledge_name || '').trim())
    setCompanyName((values.company_name || '').trim())
  }

  const handleReset = () => {
    searchForm.resetFields()
    setPage(1)
    setKnowledgeName('')
    setCompanyName('')
  }

  const handleCreate = async (values: BrandKnowledgeCreatePayload) => {
    setSubmitting(true)
    try {
      await createBrandKnowledge(values)
      message.success('新增成功')
      setCreateOpen(false)
      // 新增后回到第一页查看最新记录（列表按 id desc）
      if (page !== 1) setPage(1)
      else fetchData()
    } catch {
      // 失败提示已由拦截器弹出，保持 Drawer 打开供用户修改重试
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (record: BrandKnowledgeItem) => {
    try {
      await deleteBrandKnowledge(record.id)
      message.success('删除成功')
      // 删除当前页最后一条时回退一页，否则原地刷新
      if (items.length === 1 && page > 1) {
        setPage((p) => p - 1)
      } else {
        fetchData()
      }
    } catch {
      // 失败提示已由拦截器弹出
    }
  }

  const columns: ColumnsType<BrandKnowledgeItem> = [
    {
      title: '知识库名称',
      dataIndex: 'knowledge_name',
      key: 'knowledge_name',
      ellipsis: true,
      render: (value: string, record) => (
        <Button
          type="link"
          style={{ padding: 0 }}
          onClick={() => setDetailRecord(record)}
        >
          {value}
        </Button>
      ),
    },
    {
      title: '公司名称',
      dataIndex: 'company_name',
      key: 'company_name',
      ellipsis: true,
    },
    {
      title: '公司简称',
      dataIndex: 'company_short_name',
      key: 'company_short_name',
      width: 160,
      ellipsis: true,
      render: (value?: string | null) => (value?.trim() ? value : '-'),
    },
    {
      title: '文案类型',
      dataIndex: 'copywriting_type',
      key: 'copywriting_type',
      width: 140,
      ellipsis: true,
      render: (value?: string | null) => (value?.trim() ? value : '-'),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 200,
      render: (value: string) => formatDateTime(value),
    },
    {
      title: '操作',
      key: 'action',
      width: 220,
      fixed: 'right',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" size="small" onClick={() => setDetailRecord(record)}>
            详情
          </Button>
          <Button
            type="link"
            size="small"
            onClick={() => navigate(`/material/brand-knowledge/${record.id}/edit`)}
          >
            编辑
          </Button>
          <Popconfirm
            title="删除品牌知识库"
            description="删除后将无法在写作任务中选用，确定删除吗？"
            okText="删除"
            okButtonProps={{ danger: true }}
            cancelText="取消"
            onConfirm={() => handleDelete(record)}
          >
            <Button type="link" size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <Title level={4} style={{ marginTop: 0 }}>
        品牌知识库
      </Title>

      {/* 搜索 / 筛选区 */}
      <Form
        form={searchForm}
        layout="inline"
        style={{ marginBottom: 16, rowGap: 12 }}
        onFinish={handleSearch}
      >
        <Form.Item name="knowledge_name" label="知识库名称">
          <Input
            placeholder="按知识库名称筛选"
            allowClear
            style={{ width: 200 }}
            onPressEnter={handleSearch}
          />
        </Form.Item>
        <Form.Item name="company_name" label="公司名称">
          <Input
            placeholder="按公司名称筛选"
            allowClear
            style={{ width: 200 }}
            onPressEnter={handleSearch}
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

      {/* 操作区 */}
      <div style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateOpen(true)}
        >
          新增知识库
        </Button>
      </div>

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
      <Table<BrandKnowledgeItem>
        rowKey="id"
        columns={columns}
        dataSource={items}
        loading={loading}
        scroll={{ x: 1000 }}
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

      {/* 新增 Drawer */}
      <BrandKnowledgeFormDrawer
        open={createOpen}
        confirmLoading={submitting}
        onClose={() => setCreateOpen(false)}
        onSubmit={handleCreate}
      />

      {/* 详情 Drawer（只读） */}
      <Drawer
        title="品牌知识库详情"
        width={520}
        open={detailRecord !== null}
        onClose={() => setDetailRecord(null)}
        extra={
          detailRecord && (
            <Button
              type="primary"
              onClick={() =>
                navigate(`/material/brand-knowledge/${detailRecord.id}/edit`)
              }
            >
              编辑
            </Button>
          )
        }
      >
        {detailRecord && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="知识库名称">
              {detailRecord.knowledge_name}
            </Descriptions.Item>
            <Descriptions.Item label="公司名称">
              {detailRecord.company_name}
            </Descriptions.Item>
            <Descriptions.Item label="公司简称">
              {detailRecord.company_short_name?.trim() || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="文案类型">
              {detailRecord.copywriting_type?.trim() || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="创作方向">
              {renderText(detailRecord.creation_direction)}
            </Descriptions.Item>
            <Descriptions.Item label="产品服务">
              {renderText(detailRecord.product_service)}
            </Descriptions.Item>
            <Descriptions.Item label="产品特点">
              {renderText(detailRecord.product_features)}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {formatDateTime(detailRecord.created_at)}
            </Descriptions.Item>
            <Descriptions.Item label="更新时间">
              {formatDateTime(detailRecord.updated_at)}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  )
}
