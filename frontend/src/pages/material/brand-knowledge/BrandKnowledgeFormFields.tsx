import { Form, Input } from 'antd'

const { TextArea } = Input

/**
 * 品牌知识库表单字段（新增 Drawer 与编辑页共用）。
 *
 * 字段严格对齐 docs/api-contract.md：knowledge_name / company_name 必填，
 * company_short_name / copywriting_type 为短文本（Input），
 * creation_direction / product_service / product_features 为长文本（TextArea）。
 * 必须置于父级 <Form> 之内。
 */
export default function BrandKnowledgeFormFields() {
  return (
    <>
      <Form.Item
        label="知识库名称"
        name="knowledge_name"
        rules={[
          { required: true, message: '请输入知识库名称' },
          { whitespace: true, message: '知识库名称不能为空' },
          { max: 255, message: '知识库名称长度不能超过 255 个字符' },
        ]}
      >
        <Input placeholder="请输入知识库名称" allowClear maxLength={255} />
      </Form.Item>

      <Form.Item
        label="公司名称"
        name="company_name"
        rules={[
          { required: true, message: '请输入公司名称' },
          { whitespace: true, message: '公司名称不能为空' },
          { max: 255, message: '公司名称长度不能超过 255 个字符' },
        ]}
      >
        <Input placeholder="请输入公司名称" allowClear maxLength={255} />
      </Form.Item>

      <Form.Item
        label="公司简称"
        name="company_short_name"
        rules={[{ max: 255, message: '公司简称长度不能超过 255 个字符' }]}
      >
        <Input placeholder="请输入公司简称（选填）" allowClear maxLength={255} />
      </Form.Item>

      <Form.Item
        label="文案类型"
        name="copywriting_type"
        rules={[{ max: 128, message: '文案类型长度不能超过 128 个字符' }]}
      >
        <Input placeholder="如：种草 / 测评 / 干货（选填）" allowClear maxLength={128} />
      </Form.Item>

      <Form.Item label="创作方向" name="creation_direction">
        <TextArea
          placeholder="请输入创作方向（选填）"
          allowClear
          autoSize={{ minRows: 3, maxRows: 8 }}
          showCount
          maxLength={2000}
        />
      </Form.Item>

      <Form.Item label="产品服务" name="product_service">
        <TextArea
          placeholder="请输入产品 / 服务介绍（选填）"
          allowClear
          autoSize={{ minRows: 3, maxRows: 8 }}
          showCount
          maxLength={2000}
        />
      </Form.Item>

      <Form.Item label="产品特点" name="product_features">
        <TextArea
          placeholder="请输入产品特点 / 卖点（选填）"
          allowClear
          autoSize={{ minRows: 3, maxRows: 8 }}
          showCount
          maxLength={2000}
        />
      </Form.Item>
    </>
  )
}
