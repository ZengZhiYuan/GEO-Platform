import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Form,
  Image,
  Input,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'

import { getArticle, updateArticle } from '@/api/article'
import type {
  ArticleEditableStatus,
  ArticleStatus,
  ArticleUpdatePayload,
} from '@/types/workspace'
import {
  ArticleEditableStatusOptions,
  ArticleStatusColorMap,
  getArticleStatusLabel,
} from '@/utils/enums'

const { Title } = Typography
const { TextArea } = Input

const LIST_PATH = '/workspace/articles'

/** 表单值：状态限定为人工可切换的三种。 */
interface ArticleEditFormValues {
  article_title: string
  cover_image_url?: string
  content?: string
  status: ArticleEditableStatus
}

/** 判断状态是否为人工可切换状态（待审核 / 正常 / 禁用）。 */
function isEditableStatus(value: ArticleStatus): value is ArticleEditableStatus {
  return (
    value === 'pending_review' || value === 'normal' || value === 'disabled'
  )
}

/** 文章编辑页（/workspace/articles/:id/edit）。 */
export default function ArticleEditPage() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const numericId = Number(id)
  const validId = Number.isInteger(numericId) && numericId > 0

  const [form] = Form.useForm<ArticleEditFormValues>()
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  // 原始系统状态（generating / failed）与错误信息，仅用于提示展示
  const [originStatus, setOriginStatus] = useState<ArticleStatus | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // 实时预览封面图
  const coverUrl = Form.useWatch('cover_image_url', form)

  const fetchDetail = useCallback(async () => {
    if (!validId) return
    setLoading(true)
    setLoadError(false)
    try {
      const data = await getArticle(numericId)
      setOriginStatus(data.status)
      setErrorMessage(data.error_message ?? null)
      form.setFieldsValue({
        article_title: data.article_title ?? '',
        cover_image_url: data.cover_image_url ?? undefined,
        content: data.content ?? undefined,
        // 系统态（generating / failed）默认落到「待审核」，由人工确认后保存
        status: isEditableStatus(data.status) ? data.status : 'pending_review',
      })
    } catch {
      // 错误提示已由 axios 拦截器统一弹出，这里仅标记错误态
      setLoadError(true)
    } finally {
      setLoading(false)
    }
  }, [validId, numericId, form])

  useEffect(() => {
    fetchDetail()
  }, [fetchDetail])

  const handleSubmit = async (values: ArticleEditFormValues) => {
    setSubmitting(true)
    try {
      const payload: ArticleUpdatePayload = {
        article_title: values.article_title.trim(),
        cover_image_url: values.cover_image_url?.trim() || null,
        content: values.content ?? null,
        status: values.status,
      }
      await updateArticle(numericId, payload)
      message.success('保存成功')
      navigate(LIST_PATH)
    } catch {
      // 失败提示已由拦截器弹出，停留当前页供用户重试
    } finally {
      setSubmitting(false)
    }
  }

  if (!validId) {
    return (
      <div>
        <Title level={4} style={{ marginTop: 0 }}>
          文章编辑
        </Title>
        <Alert
          type="error"
          showIcon
          message="无效的文章 ID"
          description="请从文章清单或写作任务详情进入文章编辑页。"
          action={
            <Button size="small" onClick={() => navigate(LIST_PATH)}>
              返回列表
            </Button>
          }
        />
      </div>
    )
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(LIST_PATH)}>
          返回
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          文章编辑
        </Title>
        {originStatus && (
          <Tag color={ArticleStatusColorMap[originStatus] ?? 'default'}>
            当前状态：{getArticleStatusLabel(originStatus)}
          </Tag>
        )}
      </Space>

      {loadError && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="详情加载失败"
          description="请检查网络或后端服务后重试。"
          action={
            <Button size="small" danger onClick={fetchDetail}>
              重试
            </Button>
          }
        />
      )}

      {/* 生成中 / 生成失败 的系统态提示 */}
      {originStatus === 'generating' && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="文章仍在生成中"
          description="正文内容可能尚未生成完成，可稍后刷新查看。"
        />
      )}
      {originStatus === 'failed' && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="文章生成失败"
          description={errorMessage || '生成过程出现异常，可手动编辑后保存。'}
        />
      )}

      <Card>
        <Spin spinning={loading}>
          <Form
            form={form}
            layout="vertical"
            style={{ maxWidth: 880 }}
            onFinish={handleSubmit}
          >
            <Form.Item
              label="文章标题"
              name="article_title"
              rules={[
                { required: true, message: '请输入文章标题' },
                { whitespace: true, message: '文章标题不能为空' },
                { max: 500, message: '文章标题长度不能超过 500 个字符' },
              ]}
            >
              <Input placeholder="请输入文章标题" allowClear maxLength={500} />
            </Form.Item>

            <Form.Item
              label="封面图 URL"
              name="cover_image_url"
              rules={[
                { max: 1000, message: '封面图 URL 长度不能超过 1000 个字符' },
                {
                  type: 'url',
                  message: '请输入合法的图片 URL（http/https）',
                },
              ]}
            >
              <Input placeholder="请输入封面图 URL（http/https）" allowClear />
            </Form.Item>

            {coverUrl && (
              <Form.Item label="封面预览">
                <Image
                  src={coverUrl}
                  alt="封面预览"
                  width={200}
                  style={{ objectFit: 'cover', borderRadius: 4 }}
                  fallback="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyMDAiIGhlaWdodD0iMTIwIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjVmNWY1Ii8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZpbGw9IiNiZmJmYmYiIGZvbnQtc2l6ZT0iMTQiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj7lm77niYfml6Dms5XliqDovb08L3RleHQ+PC9zdmc+"
                />
              </Form.Item>
            )}

            <Form.Item label="正文内容" name="content">
              <TextArea
                placeholder="请输入文章正文内容"
                autoSize={{ minRows: 10, maxRows: 24 }}
              />
            </Form.Item>

            <Form.Item
              label="状态"
              name="status"
              rules={[{ required: true, message: '请选择文章状态' }]}
            >
              <Select
                style={{ width: 200 }}
                options={ArticleEditableStatusOptions}
                placeholder="请选择状态"
              />
            </Form.Item>

            <Form.Item style={{ marginBottom: 0 }}>
              <Space>
                <Button onClick={() => navigate(LIST_PATH)}>取消</Button>
                <Button type="primary" htmlType="submit" loading={submitting}>
                  保存
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Spin>
      </Card>
    </div>
  )
}
