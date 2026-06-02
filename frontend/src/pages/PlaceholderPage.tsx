import { Empty, Typography } from 'antd'

const { Title } = Typography

/**
 * 通用占位页。各业务页面在后续任务（TASK-0202 等）中替换为真实实现，
 * 当前用于打通菜单与路由切换。
 */
export default function PlaceholderPage({ title }: { title: string }) {
  return (
    <div>
      <Title level={4}>{title}</Title>
      <Empty description="页面建设中" style={{ marginTop: 80 }} />
    </div>
  )
}
