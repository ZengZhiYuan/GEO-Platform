import { useMemo } from 'react'
import { Layout, Menu, theme } from 'antd'
import type { MenuProps } from 'antd'
import {
  AppstoreOutlined,
  EditOutlined,
  FileTextOutlined,
  PictureOutlined,
  ProfileOutlined,
  ReadOutlined,
  TagsOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

const { Header, Sider, Content } = Layout

const menuItems: MenuProps['items'] = [
  {
    key: 'material',
    label: '素材中心',
    icon: <AppstoreOutlined />,
    children: [
      { key: '/material/keywords', label: '关键词库', icon: <TagsOutlined /> },
      { key: '/material/title-inspirations', label: '标题灵感', icon: <ThunderboltOutlined /> },
      { key: '/material/image-library', label: '画像图库', icon: <PictureOutlined /> },
      { key: '/material/brand-knowledge', label: '品牌知识库', icon: <ReadOutlined /> },
    ],
  },
  {
    key: 'workspace',
    label: '写作工作台',
    icon: <EditOutlined />,
    children: [
      { key: '/workspace/writing-rules', label: '写作规范', icon: <ProfileOutlined /> },
      { key: '/workspace/content-categories', label: '内容分类', icon: <AppstoreOutlined /> },
      { key: '/workspace/writing-tasks', label: '写作任务', icon: <EditOutlined /> },
      { key: '/workspace/articles', label: '文章清单', icon: <FileTextOutlined /> },
    ],
  },
]

export default function MainLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken()

  // 当前选中项与展开项，根据路由派生
  const selectedKeys = useMemo(() => [location.pathname], [location.pathname])
  const openKeys = useMemo(
    () => [location.pathname.split('/')[1]].filter(Boolean),
    [location.pathname],
  )

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="light" width={220} breakpoint="lg" collapsible>
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 700,
            fontSize: 18,
          }}
        >
          实朴GEO
        </div>
        <Menu
          mode="inline"
          items={menuItems}
          selectedKeys={selectedKeys}
          defaultOpenKeys={openKeys}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: colorBgContainer, paddingInline: 24 }}>
          <span style={{ fontSize: 16, fontWeight: 600 }}>内容生成工作台</span>
        </Header>
        <Content style={{ margin: 16 }}>
          <div
            style={{
              padding: 24,
              minHeight: '100%',
              background: colorBgContainer,
              borderRadius: borderRadiusLG,
            }}
          >
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}
