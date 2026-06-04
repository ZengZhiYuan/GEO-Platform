import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Alert,
  Button,
  Card,
  Divider,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Typography,
  message,
} from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'

import { createWritingTask } from '@/api/writingTask'
import { listContentCategories } from '@/api/contentCategory'
import { listImageCategories } from '@/api/imageCategory'
import { listBrandKnowledges } from '@/api/brandKnowledge'
import { listWritingRules } from '@/api/writingRule'
import type { WritingTaskCreatePayload } from '@/types/workspace'

const { Title } = Typography

const LIST_PATH = '/workspace/writing-tasks'

/** 下拉选项统一结构。 */
interface Option {
  label: string
  value: number
}

/** 表单值：数值字段在 antd InputNumber 下为 number，可选项允许 undefined。 */
interface WritingTaskFormValues {
  task_name: string
  content_category_id: number
  distill_keywords: string
  image_category_id?: number
  article_image_count: number
  brand_knowledge_id?: number
  content_rule_id: number
  title_rule_id?: number
  ai_generate_count: number
}

/** 写作任务新增页（/workspace/writing-tasks/create）。 */
export default function WritingTaskCreatePage() {
  const navigate = useNavigate()
  const [form] = Form.useForm<WritingTaskFormValues>()

  const [submitting, setSubmitting] = useState(false)

  // 各下拉数据
  const [categoryOptions, setCategoryOptions] = useState<Option[]>([])
  const [imageCategoryOptions, setImageCategoryOptions] = useState<Option[]>([])
  const [brandOptions, setBrandOptions] = useState<Option[]>([])
  const [contentRuleOptions, setContentRuleOptions] = useState<Option[]>([])
  const [titleRuleOptions, setTitleRuleOptions] = useState<Option[]>([])

  const [optionsLoading, setOptionsLoading] = useState(false)
  const [optionsError, setOptionsError] = useState(false)

  // 一次性拉取所有选项（page_size 取较大值，覆盖常规数据量）
  const fetchOptions = useCallback(async () => {
    setOptionsLoading(true)
    setOptionsError(false)
    try {
      const [categories, imageCategories, brands, contentRules, titleRules] =
        await Promise.all([
          listContentCategories({ page: 1, page_size: 100 }),
          listImageCategories({ page: 1, page_size: 100 }),
          listBrandKnowledges({ page: 1, page_size: 100 }),
          listWritingRules({
            page: 1,
            page_size: 100,
            creation_type: 'article_creation',
          }),
          listWritingRules({
            page: 1,
            page_size: 100,
            creation_type: 'title_creation',
          }),
        ])
      setCategoryOptions(
        categories.items.map((c) => ({ label: c.group_name, value: c.id })),
      )
      setImageCategoryOptions(
        imageCategories.items.map((c) => ({
          label: c.category_name,
          value: c.id,
        })),
      )
      setBrandOptions(
        brands.items.map((b) => ({ label: b.knowledge_name, value: b.id })),
      )
      setContentRuleOptions(
        contentRules.items.map((r) => ({ label: r.rule_name, value: r.id })),
      )
      setTitleRuleOptions(
        titleRules.items.map((r) => ({ label: r.rule_name, value: r.id })),
      )
    } catch {
      // 错误提示已由 axios 拦截器统一弹出，这里仅标记错误态
      setOptionsError(true)
    } finally {
      setOptionsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchOptions()
  }, [fetchOptions])

  const handleSubmit = async (values: WritingTaskFormValues) => {
    const payload: WritingTaskCreatePayload = {
      task_name: values.task_name.trim(),
      content_category_id: values.content_category_id,
      distill_keywords: values.distill_keywords.trim(),
      image_category_id: values.image_category_id,
      article_image_count: values.article_image_count,
      brand_knowledge_id: values.brand_knowledge_id,
      content_rule_id: values.content_rule_id,
      title_rule_id: values.title_rule_id,
      ai_generate_count: values.ai_generate_count,
    }
    setSubmitting(true)
    try {
      const task = await createWritingTask(payload)
      message.success('任务创建成功')
      // 创建成功后跳转任务详情页查看生成进度
      navigate(`/workspace/writing-tasks/${task.id}`)
    } catch {
      // 失败提示已由拦截器弹出，停留当前页供用户重试
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(LIST_PATH)}>
          返回
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          创建写作任务
        </Title>
      </Space>

      {optionsError && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="选项数据加载失败"
          description="文章分类、图库、知识库或写作规范加载失败，请重试。"
          action={
            <Button size="small" danger onClick={fetchOptions}>
              重试
            </Button>
          }
        />
      )}

      <Card>
        <Form
          form={form}
          layout="vertical"
          style={{ maxWidth: 720 }}
          onFinish={handleSubmit}
          initialValues={{ article_image_count: 1, ai_generate_count: 1 }}
        >
          <Divider orientation="left" style={{ marginTop: 0 }}>
            基础信息
          </Divider>
          <Form.Item
            label="任务名称"
            name="task_name"
            rules={[
              { required: true, message: '请输入任务名称' },
              { whitespace: true, message: '任务名称不能为空' },
              { max: 255, message: '任务名称长度不能超过 255 个字符' },
            ]}
          >
            <Input placeholder="请输入任务名称" allowClear maxLength={255} />
          </Form.Item>

          <Form.Item
            label="文章分类"
            name="content_category_id"
            rules={[{ required: true, message: '请选择文章分类' }]}
          >
            <Select
              placeholder="请选择文章分类"
              loading={optionsLoading}
              showSearch
              optionFilterProp="label"
              options={categoryOptions}
            />
          </Form.Item>

          <Form.Item
            label="蒸馏训练词"
            name="distill_keywords"
            rules={[
              { required: true, message: '请输入蒸馏训练词' },
              { whitespace: true, message: '蒸馏训练词不能为空' },
              { max: 255, message: '蒸馏训练词长度不能超过 255 个字符' },
            ]}
          >
            <Input placeholder="请输入蒸馏训练词" allowClear maxLength={255} />
          </Form.Item>

          <Divider orientation="left">素材配置</Divider>
          <Form.Item label="画像图库" name="image_category_id">
            <Select
              placeholder="请选择画像图库（可选）"
              loading={optionsLoading}
              allowClear
              showSearch
              optionFilterProp="label"
              options={imageCategoryOptions}
            />
          </Form.Item>

          <Form.Item
            label="文章配图数量"
            name="article_image_count"
            rules={[{ required: true, message: '请输入文章配图数量' }]}
          >
            <InputNumber
              min={0}
              max={50}
              precision={0}
              style={{ width: '100%' }}
              placeholder="请输入文章配图数量"
            />
          </Form.Item>

          <Form.Item label="企业知识库" name="brand_knowledge_id">
            <Select
              placeholder="请选择企业知识库（可选）"
              loading={optionsLoading}
              allowClear
              showSearch
              optionFilterProp="label"
              options={brandOptions}
            />
          </Form.Item>

          <Divider orientation="left">写作指令</Divider>
          <Form.Item
            label="内容创作指令"
            name="content_rule_id"
            rules={[{ required: true, message: '请选择内容创作指令' }]}
          >
            <Select
              placeholder="请选择内容创作指令"
              loading={optionsLoading}
              showSearch
              optionFilterProp="label"
              options={contentRuleOptions}
            />
          </Form.Item>

          <Form.Item label="标题创作指令" name="title_rule_id">
            <Select
              placeholder="请选择标题创作指令（可选）"
              loading={optionsLoading}
              allowClear
              showSearch
              optionFilterProp="label"
              options={titleRuleOptions}
            />
          </Form.Item>

          <Divider orientation="left">生成配置</Divider>
          <Form.Item
            label="AI 创作数量"
            name="ai_generate_count"
            rules={[{ required: true, message: '请输入 AI 创作数量' }]}
            extra="将根据该数量拆分为对应数量的小任务异步生成文章。"
          >
            <InputNumber
              min={1}
              max={100}
              precision={0}
              style={{ width: '100%' }}
              placeholder="请输入 AI 创作数量"
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0 }}>
            <Space>
              <Button onClick={() => navigate(LIST_PATH)}>取消</Button>
              <Button type="primary" htmlType="submit" loading={submitting}>
                确认添加
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
