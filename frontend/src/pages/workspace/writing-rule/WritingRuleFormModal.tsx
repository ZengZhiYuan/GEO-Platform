import { useEffect } from 'react'
import { Form, Input, Modal, Select } from 'antd'

import { CreationTypeOptions } from '@/utils/enums'
import type {
  WritingRuleCreatePayload,
  WritingRuleItem,
} from '@/types/workspace'

interface WritingRuleFormModalProps {
  open: boolean
  /** 编辑时的记录；为 null 表示新增。 */
  record: WritingRuleItem | null
  /** 提交按钮 loading。 */
  confirmLoading: boolean
  onCancel: () => void
  onSubmit: (values: WritingRuleCreatePayload) => void
}

/** 写作规范新增/编辑弹窗。指令内容使用长文本编辑。 */
export default function WritingRuleFormModal({
  open,
  record,
  confirmLoading,
  onCancel,
  onSubmit,
}: WritingRuleFormModalProps) {
  const [form] = Form.useForm<WritingRuleCreatePayload>()

  // 打开时回填（编辑）或重置为默认值（新增）
  useEffect(() => {
    if (!open) return
    if (record) {
      form.setFieldsValue({
        rule_name: record.rule_name,
        creation_type: record.creation_type,
        instruction_content: record.instruction_content,
      })
    } else {
      form.resetFields()
      form.setFieldsValue({ creation_type: 'article_creation' })
    }
  }, [open, record, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    onSubmit({
      ...values,
      rule_name: values.rule_name.trim(),
      instruction_content: values.instruction_content.trim(),
    })
  }

  return (
    <Modal
      title={record ? '编辑指令' : '新增指令'}
      open={open}
      width={720}
      confirmLoading={confirmLoading}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnClose
      maskClosable={false}
    >
      <Form form={form} layout="vertical" preserve={false}>
        <Form.Item
          label="指令名称"
          name="rule_name"
          rules={[
            { required: true, message: '请输入指令名称' },
            { whitespace: true, message: '指令名称不能为空' },
            { max: 255, message: '指令名称长度不能超过 255 个字符' },
          ]}
        >
          <Input placeholder="请输入指令名称" allowClear maxLength={255} />
        </Form.Item>
        <Form.Item
          label="创作类型"
          name="creation_type"
          rules={[{ required: true, message: '请选择创作类型' }]}
        >
          <Select placeholder="请选择创作类型" options={CreationTypeOptions} />
        </Form.Item>
        <Form.Item
          label="指令内容"
          name="instruction_content"
          rules={[
            { required: true, message: '请输入指令内容' },
            { whitespace: true, message: '指令内容不能为空' },
            { max: 10000, message: '指令内容长度不能超过 10000 个字符' },
          ]}
        >
          <Input.TextArea
            placeholder="请输入提示词指令内容"
            allowClear
            maxLength={10000}
            showCount
            autoSize={{ minRows: 8, maxRows: 18 }}
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}
