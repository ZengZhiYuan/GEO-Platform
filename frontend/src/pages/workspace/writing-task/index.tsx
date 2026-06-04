import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Button,
  Form,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'

import { listWritingTasks } from '@/api/writingTask'
import type { TaskStatus, WritingTaskItem } from '@/types/workspace'
import {
  TaskStatusColorMap,
  TaskStatusOptions,
  getTaskStatusLabel,
} from '@/utils/enums'
import { formatDateTime } from '@/utils/format'

const { Title } = Typography

interface SearchFormValues {
  task_name?: string
  task_status?: TaskStatus
}

/** 写作任务列表页（/workspace/writing-tasks）。 */
export default function WritingTaskPage() {
  const navigate = useNavigate()
  const [searchForm] = Form.useForm<SearchFormValues>()

  // 列表数据与状态
  const [items, setItems] = useState<WritingTaskItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)

  // 分页 + 已提交的筛选条件
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [taskName, setTaskName] = useState('')
  const [taskStatus, setTaskStatus] = useState<TaskStatus | undefined>(undefined)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setLoadError(false)
    try {
      const data = await listWritingTasks({
        page,
        page_size: pageSize,
        task_name: taskName || undefined,
        task_status: taskStatus,
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
  }, [page, pageSize, taskName, taskStatus])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleSearch = () => {
    const values = searchForm.getFieldsValue()
    setPage(1)
    setTaskName((values.task_name || '').trim())
    setTaskStatus(values.task_status)
  }

  const handleReset = () => {
    searchForm.resetFields()
    setPage(1)
    setTaskName('')
    setTaskStatus(undefined)
  }

  const columns: ColumnsType<WritingTaskItem> = [
    {
      title: '任务名称',
      dataIndex: 'task_name',
      key: 'task_name',
      ellipsis: true,
      render: (value: string, record) => (
        <Button
          type="link"
          size="small"
          style={{ padding: 0 }}
          onClick={() => navigate(`/workspace/writing-tasks/${record.id}`)}
        >
          {value}
        </Button>
      ),
    },
    {
      title: '蒸馏训练词',
      dataIndex: 'distill_keywords',
      key: 'distill_keywords',
      ellipsis: true,
      width: 200,
    },
    {
      title: 'AI 创作数量',
      dataIndex: 'ai_generate_count',
      key: 'ai_generate_count',
      width: 120,
      render: (value: number) => <Tag color="blue">{value ?? 0}</Tag>,
    },
    {
      title: '任务状态',
      dataIndex: 'task_status',
      key: 'task_status',
      width: 120,
      render: (value: TaskStatus) => (
        <Tag color={TaskStatusColorMap[value] ?? 'default'}>
          {getTaskStatusLabel(value)}
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
      width: 100,
      fixed: 'right',
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          onClick={() => navigate(`/workspace/writing-tasks/${record.id}`)}
        >
          查看详情
        </Button>
      ),
    },
  ]

  return (
    <div>
      <Title level={4} style={{ marginTop: 0 }}>
        写作任务
      </Title>

      {/* 搜索 / 筛选区 */}
      <Form
        form={searchForm}
        layout="inline"
        style={{ marginBottom: 16, rowGap: 12 }}
        onFinish={handleSearch}
      >
        <Form.Item name="task_name" label="任务名称">
          <Input
            placeholder="按任务名称搜索"
            allowClear
            style={{ width: 200 }}
            onPressEnter={handleSearch}
          />
        </Form.Item>
        <Form.Item name="task_status" label="任务状态">
          <Select
            placeholder="全部状态"
            allowClear
            style={{ width: 160 }}
            options={TaskStatusOptions}
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
          onClick={() => navigate('/workspace/writing-tasks/create')}
        >
          新增任务
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
      <Table<WritingTaskItem>
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
