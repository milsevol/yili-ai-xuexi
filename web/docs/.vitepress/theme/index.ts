import DefaultTheme from 'vitepress/theme'
import type { Theme } from 'vitepress'
import HomeTopics from './components/HomeTopics.vue'
import './custom.css'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('HomeTopics', HomeTopics)
  },
} satisfies Theme
