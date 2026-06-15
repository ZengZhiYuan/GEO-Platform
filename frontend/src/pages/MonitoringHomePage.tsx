import { Card, Result, Typography } from 'antd'

const { Paragraph } = Typography

export default function MonitoringHomePage() {
  return (
    <Card>
      <Result
        status="info"
        title="AI 应用监测基础架构已就绪"
        subTitle="监测项目、品牌、Prompt、平台和运行管理页面将在后续阶段接入。"
        extra={
          <Paragraph type="secondary" style={{ maxWidth: 640, margin: '0 auto' }}>
            当前版本保留管理端框架，并已将后端业务切换为 AI 应用监测领域。
          </Paragraph>
        }
      />
    </Card>
  )
}
