import { defineConfig } from 'vitepress'

// 本地开发默认 '/'；GitHub Pages / 打包脚本用 '/yili-ai-xuexi/'
// 可被环境变量 VITEPRESS_BASE 覆盖，例如：VITEPRESS_BASE=/yili-ai-xuexi/
const defaultBase = process.env.GITHUB_ACTIONS ? '/yili-ai-xuexi/' : '/'
const base = process.env.VITEPRESS_BASE || defaultBase

export default defineConfig({
  title: 'yili-ai-xuexi',
  description: '个人技术知识学习仓库：大数据、AI、量化交易 — 笔记 + Python 演示',
  lang: 'zh-CN',
  base,
  cleanUrls: true,
  lastUpdated: true,

  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '海豚调度', link: '/dolphin-scheduler/' },
      { text: 'Hadoop', link: '/hadoop/' },
      { text: 'Spark', link: '/spark/' },
    ],

    sidebar: {
      '/dolphin-scheduler/': [
        {
          text: '海豚调度',
          items: [
            { text: '主题入口', link: '/dolphin-scheduler/' },
            { text: '01 概述与定位', link: '/dolphin-scheduler/notes/01-概述与定位' },
            { text: '02 架构与组件', link: '/dolphin-scheduler/notes/02-架构与组件' },
            { text: '03 核心概念', link: '/dolphin-scheduler/notes/03-核心概念' },
            { text: '04 DAG 与调度', link: '/dolphin-scheduler/notes/04-DAG与调度' },
            { text: '05 任务类型详解', link: '/dolphin-scheduler/notes/05-任务类型详解' },
            { text: '06 参数与时间变量', link: '/dolphin-scheduler/notes/06-参数传递与时间变量' },
            { text: '07 资源数据源与环境', link: '/dolphin-scheduler/notes/07-资源数据源与环境' },
            { text: '08 部署与快速上手', link: '/dolphin-scheduler/notes/08-部署与快速上手' },
            { text: '09 运维与故障排查', link: '/dolphin-scheduler/notes/09-运维实践与故障排查' },
            { text: '10 生态对比与 FAQ', link: '/dolphin-scheduler/notes/10-生态对比与FAQ' },
          ],
        },
      ],
      '/hadoop/': [
        {
          text: 'Hadoop',
          items: [
            { text: '主题入口', link: '/hadoop/' },
            { text: '01 概述与定位', link: '/hadoop/notes/01-概述与定位' },
            { text: '02 HDFS 架构与原理', link: '/hadoop/notes/02-HDFS架构与原理' },
            { text: '03 HDFS 实践与运维', link: '/hadoop/notes/03-HDFS实践与运维' },
            { text: '04 MapReduce 原理与执行', link: '/hadoop/notes/04-MapReduce原理与执行' },
            { text: '05 MapReduce 进阶与优化', link: '/hadoop/notes/05-MapReduce进阶与优化' },
            { text: '06 YARN 资源管理与调度', link: '/hadoop/notes/06-YARN资源管理与调度' },
            { text: '07 Hadoop 生态组件', link: '/hadoop/notes/07-Hadoop生态组件' },
            { text: '08 部署与集群规划', link: '/hadoop/notes/08-部署与集群规划' },
            { text: '09 运维监控与故障排查', link: '/hadoop/notes/09-运维监控与故障排查' },
            { text: '10 生态对比与 FAQ', link: '/hadoop/notes/10-生态对比与FAQ' },
          ],
        },
      ],
      '/spark/': [
        {
          text: 'Spark',
          items: [
            { text: '主题入口', link: '/spark/' },
            { text: '01 概述与定位', link: '/spark/notes/01-概述与定位' },
            { text: '02 架构与运行原理', link: '/spark/notes/02-架构与运行原理' },
            { text: '03 RDD 核心抽象', link: '/spark/notes/03-RDD核心抽象' },
            { text: '04 DataFrame 与 Dataset', link: '/spark/notes/04-DataFrame与Dataset' },
            { text: '05 Spark SQL 与 Catalyst', link: '/spark/notes/05-SparkSQL与Catalyst' },
            { text: '06 Shuffle 与执行计划', link: '/spark/notes/06-Shuffle与执行计划' },
            { text: '07 部署与资源配置', link: '/spark/notes/07-部署与资源配置' },
            { text: '08 性能调优实战', link: '/spark/notes/08-性能调优实战' },
            { text: '09 Structured Streaming', link: '/spark/notes/09-StructuredStreaming' },
            { text: '10 生态对比与 FAQ', link: '/spark/notes/10-生态对比与FAQ' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/milsevol/yili-ai-xuexi' },
    ],

    search: {
      provider: 'local',
    },

    outline: {
      label: '本页目录',
    },

    docFooter: {
      prev: '上一页',
      next: '下一页',
    },

    lastUpdated: {
      text: '最后更新',
    },

    returnToTopLabel: '回到顶部',
    sidebarMenuLabel: '菜单',
    darkModeSwitchLabel: '主题',
  },
})
