import { useEffect } from 'react'
import { Form, Input, Modal, Select } from 'antd'

import { OptimizeStatusOptions } from '@/utils/enums'
import type { KeywordCreatePayload, KeywordItem } from '@/types/material'

interface KeywordFormModalProps {
  open: boolean
  /** 编辑时的记录；为 null 表示新增。 */
  record: KeywordItem | null
  /** 提交按钮 loading。 */
  confirmLoading: boolean
  onCancel: () => void
  onSubmit: (values: KeywordCreatePayload) => void
}

/** 关键词新增/编辑弹窗。 */
export default function KeywordFormModal({
  open,
  record,
  confirmLoading,
  onCancel,
  onSubmit,
}: KeywordFormModalProps) {
  const [form] = Form.useForm<KeywordCreatePayload>()

  // 打开时回填（编辑）或重置为默认值（新增）
  useEffect(() => {
    if (!open) return
    if (record) {
      form.setFieldsValue({
        main_word: record.main_word,
        optimize_status: record.optimize_status,
      })
    } else {
      form.resetFields()
      form.setFieldsValue({ optimize_status: 'not_optimized' })
    }
  }, [open, record, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    onSubmit({ ...values, main_word: values.main_word.trim() })
  }

  return (
    <Modal
      title={record ? '编辑关键词' : '新增关键词'}
      open={open}
      confirmLoading={confirmLoading}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnClose
      maskClosable={false}
    >
      <Form form={form} layout="vertical" preserve={false}>
        <Form.Item
          label="主词"
          name="main_word"
          rules={[
            { required: true, message: '请输入主词' },
            { whitespace: true, message: '主词不能为空' },
            { max: 255, message: '主词长度不能超过 255 个字符' },
          ]}
        >
          <Input placeholder="请输入主词" allowClear maxLength={255} />
        </Form.Item>
        <Form.Item
          label="优化状态"
          name="optimize_status"
          rules={[{ required: true, message: '请选择优化状态' }]}
        >
          <Select placeholder="请选择优化状态" options={OptimizeStatusOptions} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
