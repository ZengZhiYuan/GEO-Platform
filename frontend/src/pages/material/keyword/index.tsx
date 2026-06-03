import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Form,
  Input,
  Popconfirm,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'

import {
  createKeyword,
  deleteKeyword,
  listKeywords,
  updateKeyword,
} from '@/api/keyword'
import type {
  KeywordCreatePayload,
  KeywordItem,
  OptimizeStatus,
} from '@/types/material'
import {
  OptimizeStatusColorMap,
  OptimizeStatusOptions,
  getOptimizeStatusLabel,
} from '@/utils/enums'
import { formatDateTime } from '@/utils/format'
import KeywordFormModal from './KeywordFormModal'

const { Title } = Typography

interface SearchFormValues {
  main_word?: string
  optimize_status?: OptimizeStatus
}

/** 关键词库列表页（/material/keywords）。 */
export default function KeywordPage() {
  const [searchForm] = Form.useForm<SearchFormValues>()

  // 列表数据与状态
  const [items, setItems] = useState<KeywordItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)

  // 分页 + 已提交的筛选条件
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [mainWord, setMainWord] = useState('')
  const [optimizeStatus, setOptimizeStatus] = useState<OptimizeStatus | undefined>(
    undefined,
  )

  // 弹窗状态
  const [modalOpen, setModalOpen] = useState(false)
  const [editingRecord, setEditingRecord] = useState<KeywordItem | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setLoadError(false)
    try {
      const data = await listKeywords({
        page,
        page_size: pageSize,
        main_word: mainWord || undefined,
        optimize_status: optimizeStatus,
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
  }, [page, pageSize, mainWord, optimizeStatus])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleSearch = () => {
    const values = searchForm.getFieldsValue()
    setPage(1)
    setMainWord((values.main_word || '').trim())
    setOptimizeStatus(values.optimize_status)
  }

  const handleReset = () => {
    searchForm.resetFields()
    setPage(1)
    setMainWord('')
    setOptimizeStatus(undefined)
  }

  const openCreate = () => {
    setEditingRecord(null)
    setModalOpen(true)
  }

  const openEdit = (record: KeywordItem) => {
    setEditingRecord(record)
    setModalOpen(true)
  }

  const handleSubmit = async (values: KeywordCreatePayload) => {
    setSubmitting(true)
    try {
      if (editingRecord) {
        await updateKeyword(editingRecord.id, values)
        message.success('编辑成功')
      } else {
        await createKeyword(values)
        message.success('新增成功')
      }
      setModalOpen(false)
      setEditingRecord(null)
      fetchData()
    } catch {
      // 失败提示已由拦截器弹出，保持弹窗打开供用户修改重试
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (record: KeywordItem) => {
    try {
      await deleteKeyword(record.id)
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

  const columns: ColumnsType<KeywordItem> = [
    {
      title: '主词',
      dataIndex: 'main_word',
      key: 'main_word',
      ellipsis: true,
    },
    {
      title: '问题数量',
      dataIndex: 'question_count',
      key: 'question_count',
      width: 120,
    },
    {
      title: '优化状态',
      dataIndex: 'optimize_status',
      key: 'optimize_status',
      width: 140,
      render: (value: OptimizeStatus) => (
        <Tag color={OptimizeStatusColorMap[value] ?? 'default'}>
          {getOptimizeStatusLabel(value)}
        </Tag>
      ),
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
      width: 160,
      fixed: 'right',
      render: (_, record) => (
        <Space size="middle">
          <Button type="link" size="small" onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title="删除关键词"
            description={`确定删除「${record.main_word}」吗？`}
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
        关键词库
      </Title>

      {/* 搜索 / 筛选区 */}
      <Form
        form={searchForm}
        layout="inline"
        style={{ marginBottom: 16, rowGap: 12 }}
        onFinish={handleSearch}
      >
        <Form.Item name="main_word" label="主词">
          <Input
            placeholder="按主词搜索"
            allowClear
            style={{ width: 220 }}
            onPressEnter={handleSearch}
          />
        </Form.Item>
        <Form.Item name="optimize_status" label="优化状态">
          <Select
            placeholder="全部状态"
            allowClear
            style={{ width: 160 }}
            options={OptimizeStatusOptions}
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
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增关键词
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
      <Table<KeywordItem>
        rowKey="id"
        columns={columns}
        dataSource={items}
        loading={loading}
        scroll={{ x: 800 }}
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

      <KeywordFormModal
        open={modalOpen}
        record={editingRecord}
        confirmLoading={submitting}
        onCancel={() => {
          setModalOpen(false)
          setEditingRecord(null)
        }}
        onSubmit={handleSubmit}
      />
    </div>
  )
}
