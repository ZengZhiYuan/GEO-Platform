import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Form,
  Space,
  Spin,
  Typography,
  message,
} from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'

import { getBrandKnowledge, updateBrandKnowledge } from '@/api/brandKnowledge'
import type { BrandKnowledgeCreatePayload } from '@/types/material'
import { normalizeBrandKnowledgePayload } from './payload'
import BrandKnowledgeFormFields from './BrandKnowledgeFormFields'

const { Title } = Typography

const LIST_PATH = '/material/brand-knowledge'

/** 品牌知识库编辑页（/material/brand-knowledge/:id/edit）。 */
export default function BrandKnowledgeEditPage() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()
  const numericId = Number(id)
  const validId = Number.isInteger(numericId) && numericId > 0

  const [form] = Form.useForm<BrandKnowledgeCreatePayload>()
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const fetchDetail = useCallback(async () => {
    if (!validId) return
    setLoading(true)
    setLoadError(false)
    try {
      const data = await getBrandKnowledge(numericId)
      form.setFieldsValue({
        knowledge_name: data.knowledge_name,
        company_name: data.company_name,
        company_short_name: data.company_short_name ?? undefined,
        copywriting_type: data.copywriting_type ?? undefined,
        creation_direction: data.creation_direction ?? undefined,
        product_service: data.product_service ?? undefined,
        product_features: data.product_features ?? undefined,
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

  const handleSubmit = async (values: BrandKnowledgeCreatePayload) => {
    setSubmitting(true)
    try {
      await updateBrandKnowledge(numericId, normalizeBrandKnowledgePayload(values))
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
          编辑品牌知识库
        </Title>
        <Alert
          type="error"
          showIcon
          message="无效的记录 ID"
          description="请从品牌知识库列表进入编辑页。"
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
          编辑品牌知识库
        </Title>
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

      <Card>
        <Spin spinning={loading}>
          <Form
            form={form}
            layout="vertical"
            style={{ maxWidth: 720 }}
            onFinish={handleSubmit}
          >
            <BrandKnowledgeFormFields />

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
