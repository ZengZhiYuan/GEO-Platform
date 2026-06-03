import { useEffect } from 'react'
import { Form, Input, Modal } from 'antd'

import type {
  ImageCategoryCreatePayload,
  ImageCategoryItem,
} from '@/types/material'

interface ImageCategoryFormModalProps {
  open: boolean
  /** 编辑时的记录；为 null 表示新增。 */
  record: ImageCategoryItem | null
  /** 提交按钮 loading。 */
  confirmLoading: boolean
  onCancel: () => void
  onSubmit: (values: ImageCategoryCreatePayload) => void
}

/** 图库分类新增/编辑弹窗。 */
export default function ImageCategoryFormModal({
  open,
  record,
  confirmLoading,
  onCancel,
  onSubmit,
}: ImageCategoryFormModalProps) {
  const [form] = Form.useForm<ImageCategoryCreatePayload>()

  // 打开时回填（编辑）或重置（新增）
  useEffect(() => {
    if (!open) return
    if (record) {
      form.setFieldsValue({ category_name: record.category_name })
    } else {
      form.resetFields()
    }
  }, [open, record, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    onSubmit({ category_name: values.category_name.trim() })
  }

  return (
    <Modal
      title={record ? '编辑图库分类' : '新增图库分类'}
      open={open}
      confirmLoading={confirmLoading}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnClose
      maskClosable={false}
    >
      <Form form={form} layout="vertical" preserve={false}>
        <Form.Item
          label="分类名称"
          name="category_name"
          rules={[
            { required: true, message: '请输入分类名称' },
            { whitespace: true, message: '分类名称不能为空' },
            { max: 255, message: '分类名称长度不能超过 255 个字符' },
          ]}
        >
          <Input placeholder="请输入图库分类名称" allowClear maxLength={255} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
