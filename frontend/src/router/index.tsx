import { createBrowserRouter, Navigate } from 'react-router-dom'

import MainLayout from '@/layout/MainLayout'
import PlaceholderPage from '@/pages/PlaceholderPage'
import NotFoundPage from '@/pages/NotFoundPage'
import KeywordPage from '@/pages/material/keyword'
import TitleInspirationPage from '@/pages/material/title-inspiration'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { index: true, element: <Navigate to="/material/keywords" replace /> },
      // 素材中心
      { path: 'material/keywords', element: <KeywordPage /> },
      { path: 'material/title-inspirations', element: <TitleInspirationPage /> },
      { path: 'material/image-library', element: <PlaceholderPage title="画像图库" /> },
      { path: 'material/brand-knowledge', element: <PlaceholderPage title="品牌知识库" /> },
      // 写作工作台
      { path: 'workspace/writing-rules', element: <PlaceholderPage title="写作规范" /> },
      { path: 'workspace/content-categories', element: <PlaceholderPage title="内容分类" /> },
      { path: 'workspace/writing-tasks', element: <PlaceholderPage title="写作任务" /> },
      { path: 'workspace/articles', element: <PlaceholderPage title="文章清单" /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])
