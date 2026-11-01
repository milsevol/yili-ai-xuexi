/**
 * 站点主题清单（首页展示的唯一数据源）。
 * 新增主题时：在此登记，并同步 config.mts 导航 / web/docs/<主题>/index.md。
 */
export type TopicCategory = '大数据' | 'AI' | '量化交易' | '其它'

export type Topic = {
  id: string
  title: string
  category: TopicCategory
  description: string
  link: string
  /** 已有笔记章节数（可选，用于首页展示） */
  chapters?: number
  status?: 'ready' | 'coming'
}

export const topics: Topic[] = [
  {
    id: 'dolphin-scheduler',
    title: '海豚调度',
    category: '大数据',
    description:
      'Apache DolphinScheduler：DAG 工作流调度、架构与核心概念。本地 Python 演示，不依赖真实集群。',
    link: '/dolphin-scheduler/',
    chapters: 6,
    status: 'ready',
  },
]

export const categoryOrder: TopicCategory[] = ['大数据', 'AI', '量化交易', '其它']
