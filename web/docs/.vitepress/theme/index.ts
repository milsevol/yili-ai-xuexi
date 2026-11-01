import { h } from 'vue'
import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import HomeTopics from './components/HomeTopics.vue'
import './custom.css'

export default {
  extends: DefaultTheme,
  Layout() {
    return h(DefaultTheme.Layout, null, {
      // 简介放进导航标题旁，避免再叠一层顶栏把高度撑高、挡住内容
      'nav-bar-title-after': () =>
        h('span', { class: 'site-nav-tag', title: '知识学习仓库 · 笔记 + Python 演示' }, '知识学习仓库'),
    })
  },
  enhanceApp({ app }) {
    app.component('HomeTopics', HomeTopics)
  },
} satisfies Theme
