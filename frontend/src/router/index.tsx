import { createBrowserRouter, Navigate } from 'react-router-dom'

import MainLayout from '@/layout/MainLayout'
import PlaceholderPage from '@/pages/PlaceholderPage'
import NotFoundPage from '@/pages/NotFoundPage'
import KeywordPage from '@/pages/material/keyword'
import TitleInspirationPage from '@/pages/material/title-inspiration'
import ImageLibraryPage from '@/pages/material/image-library'
import ImageLibraryDetailPage from '@/pages/material/image-library/detail'
import BrandKnowledgePage from '@/pages/material/brand-knowledge'
import BrandKnowledgeEditPage from '@/pages/material/brand-knowledge/edit'
import WritingRulePage from '@/pages/workspace/writing-rule'
import ContentCategoryPage from '@/pages/workspace/content-category'
import ArticleListPage from '@/pages/workspace/article'
import ArticleEditPage from '@/pages/workspace/article/edit'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { index: true, element: <Navigate to="/material/keywords" replace /> },
      // 素材中心
      { path: 'material/keywords', element: <KeywordPage /> },
      { path: 'material/title-inspirations', element: <TitleInspirationPage /> },
      { path: 'material/image-library', element: <ImageLibraryPage /> },
      { path: 'material/image-library/:categoryId', element: <ImageLibraryDetailPage /> },
      { path: 'material/brand-knowledge', element: <BrandKnowledgePage /> },
      { path: 'material/brand-knowledge/:id/edit', element: <BrandKnowledgeEditPage /> },
      // 写作工作台
      { path: 'workspace/writing-rules', element: <WritingRulePage /> },
      { path: 'workspace/content-categories', element: <ContentCategoryPage /> },
      { path: 'workspace/writing-tasks', element: <PlaceholderPage title="写作任务" /> },
      { path: 'workspace/articles', element: <ArticleListPage /> },
      { path: 'workspace/articles/:id/edit', element: <ArticleEditPage /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])
