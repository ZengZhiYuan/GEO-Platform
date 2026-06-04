import { useEffect } from 'react'
import { Form, Input, Modal } from 'antd'

import type {
  ContentCategoryCreatePayload,
  ContentCategoryItem,
} from '@/types/workspace'

interface ContentCategoryFormModalProps {
  open: boolean
  /** 编辑时的记录；为 null 表示新增。 */
  record: ContentCategoryItem | null
  /** 提交按钮 loading。 */
  confirmLoading: boolean
  onCancel: () => void
  onSubmit: (values: ContentCategoryCreatePayload) => void
}

/** 内容分类新增/编辑弹窗。 */
export default function ContentCategoryFormModal({
  open,
  record,
  confirmLoading,
  onCancel,
  onSubmit,
}: ContentCategoryFormModalProps) {
  const [form] = Form.useForm<ContentCategoryCreatePayload>()

  // 打开时回填（编辑）或重置（新增）
  useEffect(() => {
    if (!open) return
    if (record) {
      form.setFieldsValue({ group_name: record.group_name })
    } else {
      form.resetFields()
    }
  }, [open, record, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    onSubmit({ group_name: values.group_name.trim() })
  }

  return (
    <Modal
      title={record ? '编辑分类' : '新增分类'}
      open={open}
      width={480}
      confirmLoading={confirmLoading}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnClose
      maskClosable={false}
    >
      <Form form={form} layout="vertical" preserve={false}>
        <Form.Item
          label="分类名称"
          name="group_name"
          rules={[
            { required: true, message: '请输入分类名称' },
            { whitespace: true, message: '分类名称不能为空' },
            { max: 255, message: '分类名称长度不能超过 255 个字符' },
          ]}
        >
          <Input placeholder="请输入分类名称" allowClear maxLength={255} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
