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
