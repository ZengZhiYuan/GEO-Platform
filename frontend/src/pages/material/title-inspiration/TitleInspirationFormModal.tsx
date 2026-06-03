import { useEffect } from 'react'
import { Form, Input, Modal, Select } from 'antd'

import { CollectStatusOptions } from '@/utils/enums'
import type {
  TitleInspirationCreatePayload,
  TitleInspirationItem,
} from '@/types/material'

interface TitleInspirationFormModalProps {
  open: boolean
  /** 编辑时的记录；为 null 表示新增。 */
  record: TitleInspirationItem | null
  /** 提交按钮 loading。 */
  confirmLoading: boolean
  /** 新增时默认带入的主词（从列表筛选条件继承）。 */
  defaultMainWord?: string
  onCancel: () => void
  onSubmit: (values: TitleInspirationCreatePayload) => void
}

/** 标题灵感新增/编辑弹窗。 */
export default function TitleInspirationFormModal({
  open,
  record,
  confirmLoading,
  defaultMainWord,
  onCancel,
  onSubmit,
}: TitleInspirationFormModalProps) {
  const [form] = Form.useForm<TitleInspirationCreatePayload>()

  // 打开时回填（编辑）或重置为默认值（新增）
  useEffect(() => {
    if (!open) return
    if (record) {
      form.setFieldsValue({
        main_word: record.main_word,
        question: record.question,
        collect_status: record.collect_status,
      })
    } else {
      form.resetFields()
      form.setFieldsValue({
        main_word: defaultMainWord ?? '',
        collect_status: 'not_included',
      })
    }
  }, [open, record, defaultMainWord, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    onSubmit({
      ...values,
      main_word: values.main_word.trim(),
      question: values.question.trim(),
    })
  }

  return (
    <Modal
      title={record ? '编辑问题' : '新增问题'}
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
          label="问题"
          name="question"
          rules={[
            { required: true, message: '请输入问题' },
            { whitespace: true, message: '问题不能为空' },
            { max: 500, message: '问题长度不能超过 500 个字符' },
          ]}
        >
          <Input.TextArea
            placeholder="请输入围绕主词的提问/选题"
            allowClear
            maxLength={500}
            showCount
            autoSize={{ minRows: 3, maxRows: 6 }}
          />
        </Form.Item>
        <Form.Item
          label="收录状态"
          name="collect_status"
          rules={[{ required: true, message: '请选择收录状态' }]}
        >
          <Select placeholder="请选择收录状态" options={CollectStatusOptions} />
        </Form.Item>
      </Form>
    </Modal>
  )
}
