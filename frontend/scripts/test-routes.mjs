import { readFile } from 'node:fs/promises'

const router = await readFile(new URL('../src/router/index.tsx', import.meta.url), 'utf8')
const layout = await readFile(new URL('../src/layout/MainLayout.tsx', import.meta.url), 'utf8')
const source = `${router}\n${layout}`

const forbidden = [
  ['/material', '/'].join(''),
  ['/workspace', '/'].join(''),
  ['关键词', '库'].join(''),
  ['标题', '灵感'].join(''),
  ['画像', '图库'].join(''),
  ['品牌', '知识库'].join(''),
  ['写作', '规范'].join(''),
  ['写作', '任务'].join(''),
  ['文章', '清单'].join(''),
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
