<script setup lang="ts">
import { computed, ref } from 'vue'
import { withBase } from 'vitepress'
import {
  categoryHints,
  categoryOrder,
  topics,
  type TopicCategory,
} from '../../topics'
import topicStats from '../../topic-stats.generated'

const filter = ref<'全部' | TopicCategory>('全部')

const chapterCount = (id: string) => topicStats[id] ?? 0

const countIn = (cat: TopicCategory) => topics.filter((t) => t.category === cat).length

/** topics.ts 原始下标（大数据类按此顺序 = 学习路线图顺序） */
const topicIndex = topics.reduce<Record<string, number>>((acc, t, i) => {
  acc[t.id] = i
  return acc
}, {})

const sortTopics = (list: typeof topics) =>
  [...list].sort((a, b) => {
    if (a.status === 'coming' && b.status !== 'coming') return 1
    if (b.status === 'coming' && a.status !== 'coming') return -1
    // 大数据类按 topics.ts 顺序（即学习路线图）；其他类按拼音
    if (a.category === '大数据' && b.category === '大数据') {
      return (topicIndex[a.id] ?? 0) - (topicIndex[b.id] ?? 0)
    }
    return a.title.localeCompare(b.title, 'zh-CN')
  })

/** 「全部」只展示有内容的大类；点进空类才显示空状态 */
const sections = computed(() => {
  if (filter.value === '全部') {
    return categoryOrder
      .map((category) => ({
        category,
        hint: categoryHints[category],
        items: sortTopics(topics.filter((t) => t.category === category)),
      }))
      .filter((s) => s.items.length > 0)
  }

  return [
    {
      category: filter.value,
      hint: categoryHints[filter.value],
      items: sortTopics(topics.filter((t) => t.category === filter.value)),
    },
  ]
})

const readyCount = computed(() => topics.filter((t) => t.status !== 'coming').length)
const activeHint = computed(() =>
  filter.value === '全部' ? '选择左侧大类，或直接进入主题' : categoryHints[filter.value],
)
</script>

<template>
  <div class="home-page">
    <div class="home-shell">
      <aside class="home-cats" aria-label="知识大类">
        <p class="home-cats__label">知识大类</p>
        <button
          type="button"
          class="home-cat"
          :class="{ 'is-active': filter === '全部' }"
          @click="filter = '全部'"
        >
          <span class="home-cat__name">全部</span>
          <span class="home-cat__count">{{ topics.length }}</span>
        </button>
        <button
          v-for="cat in categoryOrder"
          :key="cat"
          type="button"
          class="home-cat"
          :class="{ 'is-active': filter === cat, 'is-empty': countIn(cat) === 0 }"
          @click="filter = cat"
        >
          <span class="home-cat__name">{{ cat }}</span>
          <span class="home-cat__count">{{ countIn(cat) }}</span>
        </button>
      </aside>

      <main class="home-main">
        <div class="home-main__bar">
          <div>
            <h1 class="home-main__title">
              {{ filter === '全部' ? '主题' : filter }}
            </h1>
            <p class="home-main__hint">{{ activeHint }} · {{ readyCount }} 个可学</p>
          </div>
        </div>

        <div v-if="filter === '全部' || filter === '大数据'" class="home-roadmap">
          <div class="home-roadmap__title">📚 大数据学习路线图（建议从上到下依次学习）</div>
          <div class="home-roadmap__flow">
            <span class="home-roadmap__step">① Hadoop 底座</span>
            <span class="home-roadmap__arrow">→</span>
            <span class="home-roadmap__step">② Hive 数仓 SQL</span>
            <span class="home-roadmap__arrow">→</span>
            <span class="home-roadmap__step">③ Spark / ④ Flink 计算</span>
            <span class="home-roadmap__arrow">→</span>
            <span class="home-roadmap__step">⑤ Kafka 实时管道</span>
            <span class="home-roadmap__arrow">→</span>
            <span class="home-roadmap__step">⑥ 湖仓一体 Iceberg</span>
            <span class="home-roadmap__arrow">→</span>
            <span class="home-roadmap__step">⑦ HBase / ⑧ ClickHouse 数据访问</span>
            <span class="home-roadmap__arrow">→</span>
            <span class="home-roadmap__step">⑨ 海豚调度编排</span>
          </div>
        </div>

        <template v-for="section in sections" :key="section.category">
          <div v-if="filter === '全部'" class="home-group__label">{{ section.category }}</div>

          <div v-if="section.items.length" class="home-grid">
            <a
              v-for="topic in section.items"
              :key="topic.id"
              class="topic-row"
              :href="withBase(topic.link)"
            >
              <div class="topic-row__body">
                <div class="topic-row__top">
                  <h2 class="topic-row__title">{{ topic.title }}</h2>
                  <span v-if="chapterCount(topic.id)" class="topic-row__chapters">{{ chapterCount(topic.id) }} 章</span>
                </div>
                <p class="topic-row__desc">{{ topic.description }}</p>
              </div>
              <span class="topic-row__go" aria-hidden="true">→</span>
            </a>
          </div>

          <p v-else class="home-empty">该类暂无主题，后续补充。</p>
        </template>

        <p v-if="filter === '全部' && sections.length === 0" class="home-empty">
          还没有主题，先在仓库中新增一个吧。
        </p>
      </main>
    </div>
  </div>
</template>
