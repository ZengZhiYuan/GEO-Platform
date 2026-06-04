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
  createWritingRule,
  deleteWritingRule,
  listWritingRules,
  updateWritingRule,
} from '@/api/writingRule'
import type {
  CreationType,
  WritingRuleCreatePayload,
  WritingRuleItem,
} from '@/types/workspace'
import {
  CreationTypeColorMap,
  CreationTypeOptions,
  getCreationTypeLabel,
} from '@/utils/enums'
import { formatDateTime } from '@/utils/format'
import WritingRuleFormModal from './WritingRuleFormModal'

const { Title, Paragraph } = Typography

interface SearchFormValues {
  rule_name?: string
  creation_type?: CreationType
}

/** 写作规范列表页（/workspace/writing-rules）。 */
export default function WritingRulePage() {
  const [searchForm] = Form.useForm<SearchFormValues>()

  // 列表数据与状态
  const [items, setItems] = useState<WritingRuleItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)

  // 分页 + 已提交的筛选条件
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [ruleName, setRuleName] = useState('')
  const [creationType, setCreationType] = useState<CreationType | undefined>(
    undefined,
  )

  // 弹窗状态
  const [modalOpen, setModalOpen] = useState(false)
  const [editingRecord, setEditingRecord] = useState<WritingRuleItem | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setLoadError(false)
    try {
      const data = await listWritingRules({
        page,
        page_size: pageSize,
        rule_name: ruleName || undefined,
        creation_type: creationType,
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
  }, [page, pageSize, ruleName, creationType])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleSearch = () => {
    const values = searchForm.getFieldsValue()
    setPage(1)
    setRuleName((values.rule_name || '').trim())
    setCreationType(values.creation_type)
  }

  const handleReset = () => {
    searchForm.resetFields()
    setPage(1)
    setRuleName('')
    setCreationType(undefined)
  }

  const openCreate = () => {
    setEditingRecord(null)
    setModalOpen(true)
  }

  const openEdit = (record: WritingRuleItem) => {
    setEditingRecord(record)
    setModalOpen(true)
  }

  const handleSubmit = async (values: WritingRuleCreatePayload) => {
    setSubmitting(true)
    try {
      if (editingRecord) {
        await updateWritingRule(editingRecord.id, values)
        message.success('编辑成功')
      } else {
        await createWritingRule(values)
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

  const handleDelete = async (record: WritingRuleItem) => {
    try {
      await deleteWritingRule(record.id)
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

  const columns: ColumnsType<WritingRuleItem> = [
    {
      title: '指令名称',
      dataIndex: 'rule_name',
      key: 'rule_name',
      width: 220,
      ellipsis: true,
    },
    {
      title: '创作类型',
      dataIndex: 'creation_type',
      key: 'creation_type',
      width: 140,
      render: (value: CreationType) => (
        <Tag color={CreationTypeColorMap[value] ?? 'default'}>
          {getCreationTypeLabel(value)}
        </Tag>
      ),
    },
    {
      title: '指令内容',
      dataIndex: 'instruction_content',
      key: 'instruction_content',
      render: (value: string) => (
        <Paragraph
          style={{ marginBottom: 0 }}
          ellipsis={{ rows: 2, tooltip: value }}
        >
          {value}
        </Paragraph>
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
            title="删除指令"
            description={`确定删除「${record.rule_name}」吗？`}
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
        写作规范
      </Title>

      {/* 搜索 / 筛选区 */}
      <Form
        form={searchForm}
        layout="inline"
        style={{ marginBottom: 16, rowGap: 12 }}
        onFinish={handleSearch}
      >
        <Form.Item name="rule_name" label="指令名称">
          <Input
            placeholder="按指令名称搜索"
            allowClear
            style={{ width: 220 }}
            onPressEnter={handleSearch}
          />
        </Form.Item>
        <Form.Item name="creation_type" label="创作类型">
          <Select
            placeholder="全部类型"
            allowClear
            style={{ width: 160 }}
            options={CreationTypeOptions}
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
          新增指令
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
      <Table<WritingRuleItem>
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

      <WritingRuleFormModal
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
