import { useEffect } from 'react'
import { Form, Input, Modal } from 'antd'

interface ImageAssetFormValues {
  image_url: string
}

interface ImageAssetFormModalProps {
  open: boolean
  /** 提交按钮 loading。 */
  confirmLoading: boolean
  onCancel: () => void
  onSubmit: (values: ImageAssetFormValues) => void
}

// 简单 URL 校验：必须以 http(s):// 开头
const URL_PATTERN = /^https?:\/\/.+/i

/** 新增图片 URL 弹窗。 */
export default function ImageAssetFormModal({
  open,
  confirmLoading,
  onCancel,
  onSubmit,
}: ImageAssetFormModalProps) {
  const [form] = Form.useForm<ImageAssetFormValues>()

  useEffect(() => {
    if (open) form.resetFields()
  }, [open, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    onSubmit({ image_url: values.image_url.trim() })
  }

  return (
    <Modal
      title="新增图片"
      open={open}
      confirmLoading={confirmLoading}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnClose
      maskClosable={false}
    >
      <Form form={form} layout="vertical" preserve={false}>
        <Form.Item
          label="图片 URL"
          name="image_url"
          rules={[
            { required: true, message: '请输入图片 URL' },
            { whitespace: true, message: '图片 URL 不能为空' },
            { max: 2048, message: '图片 URL 长度不能超过 2048 个字符' },
            { pattern: URL_PATTERN, message: '请输入以 http:// 或 https:// 开头的有效链接' },
          ]}
        >
          <Input.TextArea
            placeholder="请输入图片链接，如 https://example.com/cover.png"
            allowClear
            maxLength={2048}
            autoSize={{ minRows: 2, maxRows: 4 }}
          />
        </Form.Item>
      </Form>
    </Modal>
  )
}
