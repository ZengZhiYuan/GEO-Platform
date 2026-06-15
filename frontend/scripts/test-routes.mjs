import { readFile } from 'node:fs/promises'

const router = await readFile(new URL('../src/router/index.tsx', import.meta.url), 'utf8')
const layout = await readFile(new URL('../src/layout/MainLayout.tsx', import.meta.url), 'utf8')
const source = `${router}\n${layout}`

const forbidden = [
  '/material/',
  '/workspace/',
  '关键词库',
  '标题灵感',
  '画像图库',
  '品牌知识库',
  '写作规范',
  '写作任务',
  '文章清单',
]

if (!source.includes('/monitoring')) {
  throw new Error('monitoring route is missing')
}

if (!source.includes('监测概览')) {
  throw new Error('monitoring menu item is missing')
}

for (const value of forbidden) {
  if (source.includes(value)) {
    throw new Error(`legacy route or label remains: ${value}`)
  }
}
