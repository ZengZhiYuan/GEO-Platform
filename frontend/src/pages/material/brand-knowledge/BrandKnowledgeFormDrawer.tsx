import { useEffect } from 'react'
import { Button, Drawer, Form, Space } from 'antd'

import type { BrandKnowledgeCreatePayload } from '@/types/material'
import { normalizeBrandKnowledgePayload } from './payload'
import BrandKnowledgeFormFields from './BrandKnowledgeFormFields'

interface BrandKnowledgeFormDrawerProps {
  open: boolean
  /** 提交按钮 loading。 */
  confirmLoading: boolean
  onClose: () => void
  onSubmit: (values: BrandKnowledgeCreatePayload) => void
}

/**
 * 品牌知识库新增 Drawer。
 * 字段较多，使用抽屉承载（编辑使用独立页面 /material/brand-knowledge/:id/edit）。
 */
export default function BrandKnowledgeFormDrawer({
  open,
  confirmLoading,
  onClose,
  onSubmit,
}: BrandKnowledgeFormDrawerProps) {
  const [form] = Form.useForm<BrandKnowledgeCreatePayload>()

  // 打开时重置表单
  useEffect(() => {
    if (open) form.resetFields()
  }, [open, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    onSubmit(normalizeBrandKnowledgePayload(values))
  }

  return (
    <Drawer
      title="新增品牌知识库"
      width={520}
      open={open}
      onClose={onClose}
      destroyOnClose
      maskClosable={false}
      footer={
        <Space style={{ float: 'right' }}>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" loading={confirmLoading} onClick={handleOk}>
            提交
          </Button>
        </Space>
      }
    >
      <Form form={form} layout="vertical" preserve={false}>
        <BrandKnowledgeFormFields />
      </Form>
    </Drawer>
  )
}
