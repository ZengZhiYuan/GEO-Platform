import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Button,
  Form,
  Input,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { PlusOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'

import {
  createImageCategory,
  deleteImageCategory,
  listImageCategories,
  updateImageCategory,
} from '@/api/imageCategory'
import type {
  ImageCategoryCreatePayload,
  ImageCategoryItem,
} from '@/types/material'
import { formatDateTime } from '@/utils/format'
import ImageCategoryFormModal from './ImageCategoryFormModal'

const { Title } = Typography

interface SearchFormValues {
  category_name?: string
}

/** 画像图库分类列表页（/material/image-library）。 */
export default function ImageLibraryPage() {
  const navigate = useNavigate()
  const [searchForm] = Form.useForm<SearchFormValues>()

  // 列表数据与状态
  const [items, setItems] = useState<ImageCategoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)

  // 分页 + 已提交的筛选条件
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [categoryName, setCategoryName] = useState('')

  // 弹窗状态
  const [modalOpen, setModalOpen] = useState(false)
  const [editingRecord, setEditingRecord] = useState<ImageCategoryItem | null>(
    null,
  )
  const [submitting, setSubmitting] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setLoadError(false)
    try {
      const data = await listImageCategories({
        page,
        page_size: pageSize,
        category_name: categoryName || undefined,
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
  }, [page, pageSize, categoryName])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleSearch = () => {
    const values = searchForm.getFieldsValue()
    setPage(1)
    setCategoryName((values.category_name || '').trim())
  }

  const handleReset = () => {
    searchForm.resetFields()
    setPage(1)
    setCategoryName('')
  }

  const openCreate = () => {
    setEditingRecord(null)
    setModalOpen(true)
  }

  const openEdit = (record: ImageCategoryItem) => {
    setEditingRecord(record)
    setModalOpen(true)
  }

  const goDetail = (record: ImageCategoryItem) => {
    // 携带分类名以便详情页直接展示，详情页同时会兜底拉取分类详情
    navigate(`/material/image-library/${record.id}`, {
      state: { category_name: record.category_name },
    })
  }

  const handleSubmit = async (values: ImageCategoryCreatePayload) => {
    setSubmitting(true)
    try {
      if (editingRecord) {
        await updateImageCategory(editingRecord.id, values)
        message.success('编辑成功')
      } else {
        await createImageCategory(values)
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

  const handleDelete = async (record: ImageCategoryItem) => {
    try {
      await deleteImageCategory(record.id)
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

  const columns: ColumnsType<ImageCategoryItem> = [
    {
      title: '分类名称',
      dataIndex: 'category_name',
      key: 'category_name',
      ellipsis: true,
      render: (value: string, record) => (
        <Button type="link" style={{ padding: 0 }} onClick={() => goDetail(record)}>
          {value}
        </Button>
      ),
    },
    {
      title: '图片数量',
      dataIndex: 'image_count',
      key: 'image_count',
      width: 140,
      render: (value: number) => <Tag color="blue">{value ?? 0}</Tag>,
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
          <Button type="link" size="small" onClick={() => goDetail(record)}>
            查看图片
          </Button>
          <Button type="link" size="small" onClick={() => openEdit(record)}>
            编辑
          </Button>
          <Popconfirm
            title="删除图库分类"
            description="删除后该分类下图片将无法访问，确定删除吗？"
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
        画像图库
      </Title>

      {/* 搜索 / 筛选区 */}
      <Form
        form={searchForm}
        layout="inline"
        style={{ marginBottom: 16, rowGap: 12 }}
        onFinish={handleSearch}
      >
        <Form.Item name="category_name" label="分类名称">
          <Input
            placeholder="按分类名称筛选"
            allowClear
            style={{ width: 220 }}
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
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新增分类
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
      <Table<ImageCategoryItem>
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

      <ImageCategoryFormModal
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
