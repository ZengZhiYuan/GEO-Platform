import { createBrowserRouter, Navigate } from 'react-router-dom'

import MainLayout from '@/layout/MainLayout'
import MonitoringHomePage from '@/pages/MonitoringHomePage'
import NotFoundPage from '@/pages/NotFoundPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      { index: true, element: <Navigate to="/monitoring" replace /> },
      { path: 'monitoring', element: <MonitoringHomePage /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])
