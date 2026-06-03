import { useCallback, useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Empty,
  Image,
  List,
  Popconfirm,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  ArrowLeftOutlined,
  CopyOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons'

import { getImageCategory } from '@/api/imageCategory'
import {
  createImageAsset,
  deleteImageAsset,
  listImageAssets,
} from '@/api/imageAsset'
import type { ImageAssetItem } from '@/types/material'
import { formatDateTime } from '@/utils/format'
import ImageAssetFormModal from './ImageAssetFormModal'

const { Title, Text } = Typography

/** 复制文本到剪贴板，兼容非安全上下文（无 clipboard API）的降级方案。 */
async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // 落到降级方案
  }
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(textarea)
    return ok
  } catch {
    return false
  }
}

/** 画像图库图片详情页（/material/image-library/:categoryId）。 */
export default function ImageLibraryDetailPage() {
  const { categoryId } = useParams<{ categoryId: string }>()
  const navigate = useNavigate()
  const location = useLocation()

  const numericCategoryId = Number(categoryId)
  const invalidCategoryId = !categoryId || Number.isNaN(numericCategoryId)

  // 分类名优先取列表页跳转时携带的 state，兜底从接口拉取
  const stateName = (location.state as { category_name?: string } | null)
    ?.category_name
  const [categoryName, setCategoryName] = useState<string>(stateName ?? '')

  // 列表数据与状态
  const [items, setItems] = useState<ImageAssetItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)

  // 分页
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(12)

  // 新增弹窗
  const [modalOpen, setModalOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // 拉取分类名（仅当未通过 state 带入时）
  useEffect(() => {
    if (invalidCategoryId || stateName) return
    getImageCategory(numericCategoryId)
      .then((data) => setCategoryName(data.category_name))
      .catch(() => {
        // 分类详情失败不阻塞图片列表，标题降级展示
      })
  }, [invalidCategoryId, numericCategoryId, stateName])

  const fetchData = useCallback(async () => {
    if (invalidCategoryId) return
    setLoading(true)
    setLoadError(false)
    try {
      const data = await listImageAssets({
        page,
        page_size: pageSize,
        category_id: numericCategoryId,
      })
      setItems(data.items)
      setTotal(data.total)
    } catch {
      // 错误提示已由 axios 拦截器统一弹出，这里仅标记错误态
      setLoadError(true)
      setItems([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [invalidCategoryId, numericCategoryId, page, pageSize])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleSubmit = async (values: { image_url: string }) => {
    setSubmitting(true)
    try {
      await createImageAsset({
        category_id: numericCategoryId,
        image_url: values.image_url,
      })
      message.success('新增成功')
      setModalOpen(false)
      // 回到第一页查看最新录入（若已在第一页则直接刷新）
      if (page !== 1) {
        setPage(1)
      } else {
        fetchData()
      }
    } catch {
      // 失败提示已由拦截器弹出，保持弹窗打开供修改重试
    } finally {
      setSubmitting(false)
    }
  }

  const handleCopy = async (url: string) => {
    const ok = await copyToClipboard(url)
    if (ok) {
      message.success('已复制图片 URL')
    } else {
      message.error('复制失败，请手动复制')
    }
  }

  const handleDelete = async (record: ImageAssetItem) => {
    try {
      await deleteImageAsset(record.id)
      message.success('删除成功')
      if (items.length === 1 && page > 1) {
        setPage((p) => p - 1)
      } else {
        fetchData()
      }
    } catch {
      // 失败提示已由拦截器弹出
    }
  }

  if (invalidCategoryId) {
    return (
      <div>
        <Title level={4} style={{ marginTop: 0 }}>
          图片详情
        </Title>
        <Alert
          type="error"
          showIcon
          message="分类参数无效"
          description="无法识别当前图库分类，请返回图库列表重新进入。"
          action={
            <Button size="small" onClick={() => navigate('/material/image-library')}>
              返回图库
            </Button>
          }
        />
      </div>
    )
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }} align="center">
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/material/image-library')}
        >
          返回图库
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          {categoryName ? `图片详情 - ${categoryName}` : '图片详情'}
        </Title>
      </Space>

      {/* 操作区 */}
      <div style={{ marginBottom: 16 }}>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setModalOpen(true)}
        >
          新增图片
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
            <Button size="small" danger icon={<ReloadOutlined />} onClick={fetchData}>
              重试
            </Button>
          }
        />
      )}

      {/* 图片网格 + 分页 */}
      <Spin spinning={loading}>
        {!loading && items.length === 0 ? (
          <Empty description="暂无图片，点击「新增图片」录入图片 URL" />
        ) : (
          <Image.PreviewGroup>
            <List
              grid={{ gutter: 16, xs: 1, sm: 2, md: 3, lg: 4, xl: 4, xxl: 6 }}
              dataSource={items}
              pagination={{
                current: page,
                pageSize,
                total,
                showSizeChanger: true,
                pageSizeOptions: ['12', '24', '48'],
                showTotal: (t) => `共 ${t} 条`,
                onChange: (nextPage, nextPageSize) => {
                  setPage(nextPage)
                  setPageSize(nextPageSize)
                },
              }}
              renderItem={(item) => (
                <List.Item>
                  <Card
                    size="small"
                    styles={{ body: { padding: 12 } }}
                    cover={
                      <div
                        style={{
                          height: 160,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          background: '#fafafa',
                          overflow: 'hidden',
                        }}
                      >
                        <Image
                          src={item.image_url}
                          alt={`image-${item.id}`}
                          height={160}
                          style={{ objectFit: 'contain' }}
                        />
                      </div>
                    }
                    actions={[
                      <Button
                        key="copy"
                        type="link"
                        size="small"
                        icon={<CopyOutlined />}
                        onClick={() => handleCopy(item.image_url)}
                      >
                        复制URL
                      </Button>,
                      <Popconfirm
                        key="delete"
                        title="删除图片"
                        description="确定删除该图片吗？"
                        okText="删除"
                        okButtonProps={{ danger: true }}
                        cancelText="取消"
                        onConfirm={() => handleDelete(item)}
                      >
                        <Button type="link" size="small" danger>
                          删除
                        </Button>
                      </Popconfirm>,
                    ]}
                  >
                    <Space direction="vertical" size={4} style={{ width: '100%' }}>
                      <Text
                        ellipsis={{ tooltip: item.image_url }}
                        style={{ width: '100%' }}
                      >
                        {item.image_url}
                      </Text>
                      <Space size={8}>
                        <Tag color="blue">使用 {item.use_count ?? 0} 次</Tag>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {formatDateTime(item.created_at)}
                        </Text>
                      </Space>
                    </Space>
                  </Card>
                </List.Item>
              )}
            />
          </Image.PreviewGroup>
        )}
      </Spin>

      <ImageAssetFormModal
        open={modalOpen}
        confirmLoading={submitting}
        onCancel={() => setModalOpen(false)}
        onSubmit={handleSubmit}
      />
    </div>
  )
}
