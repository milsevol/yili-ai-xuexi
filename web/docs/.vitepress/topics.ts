/**
 * 站点主题清单（首页展示的唯一数据源）。
 * 大类定义见仓库根目录「知识框架.md」。
 * 新增主题时：在此登记，并同步 config.mts 导航 / web/docs/<主题>/index.md。
 */
export type TopicCategory =
  | '基础语言'
  | '大数据'
  | 'AI技术'
  | 'AI应用'
  | '金融技术'

export type Topic = {
  id: string
  title: string
  category: TopicCategory
  description: string
  link: string
  /** 章数由 sync-notes 扫描 notes/<主题>/notes/*.md 自动生成，勿在此手写 */
  status?: 'ready' | 'coming'
}

/** 大类顺序（首页筛选与分组固定按此顺序） */
export const categoryOrder: TopicCategory[] = [
  '基础语言',
  '大数据',
  'AI技术',
  'AI应用',
  '金融技术',
]

export const categoryHints: Record<TopicCategory, string> = {
  基础语言: 'Python、Java、SQL、Shell 等语言基础',
  大数据: '调度、数仓、消息队列、计算引擎等',
  AI技术: '模型、RAG、向量库、Agent 等技术能力',
  AI应用: '业务场景与落地用法',
  金融技术: '量化交易、财富管理等金融域',
}

export const topics: Topic[] = [
  {
    id: 'dolphin-scheduler',
    title: '海豚调度',
    category: '大数据',
    description:
      'Apache DolphinScheduler：从概述到部署运维与选型。浏览器可视化交互演示，不依赖真实集群。',
    link: '/dolphin-scheduler/',
    status: 'ready',
  },
]
