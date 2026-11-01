<script setup lang="ts">
import { computed, ref } from 'vue'
import { withBase } from 'vitepress'
import { categoryOrder, topics, type TopicCategory } from '../../topics'

const filter = ref<'全部' | TopicCategory>('全部')

const categories = computed(() => {
  const present = new Set(topics.map((t) => t.category))
  return categoryOrder.filter((c) => present.has(c))
})

const visible = computed(() => {
  const list =
    filter.value === '全部'
      ? topics
      : topics.filter((t) => t.category === filter.value)
  return [...list].sort((a, b) => {
    if (a.status === 'coming' && b.status !== 'coming') return 1
    if (b.status === 'coming' && a.status !== 'coming') return -1
    return a.title.localeCompare(b.title, 'zh-CN')
  })
})

const readyCount = computed(() => topics.filter((t) => t.status !== 'coming').length)
</script>

<template>
  <section class="home-topics">
    <div class="home-topics__inner">
      <header class="home-topics__header">
        <p class="home-topics__eyebrow">主题目录</p>
        <h2 class="home-topics__title">按主题进入学习</h2>
        <p class="home-topics__lead">
          现有 {{ readyCount }} 个可学主题。主题变多后仍按分类筛选；点进主题读笔记，演示在本地用 Python 跑。
        </p>
      </header>

      <div v-if="categories.length > 1" class="home-topics__filters" role="tablist" aria-label="按分类筛选">
        <button
          type="button"
          class="home-topics__chip"
          :class="{ 'is-active': filter === '全部' }"
          @click="filter = '全部'"
        >
          全部
          <span class="home-topics__count">{{ topics.length }}</span>
        </button>
        <button
          v-for="cat in categories"
          :key="cat"
          type="button"
          class="home-topics__chip"
          :class="{ 'is-active': filter === cat }"
          @click="filter = cat"
        >
          {{ cat }}
          <span class="home-topics__count">{{ topics.filter((t) => t.category === cat).length }}</span>
        </button>
      </div>

      <div class="home-topics__grid">
        <component
          :is="topic.status === 'coming' ? 'div' : 'a'"
          v-for="topic in visible"
          :key="topic.id"
          class="topic-card"
          :class="{ 'is-coming': topic.status === 'coming' }"
          v-bind="
            topic.status === 'coming'
              ? { role: 'note', 'aria-label': `${topic.title}（即将推出）` }
              : { href: withBase(topic.link) }
          "
        >
          <div class="topic-card__meta">
            <span class="topic-card__cat">{{ topic.category }}</span>
            <span v-if="topic.chapters" class="topic-card__chapters">{{ topic.chapters }} 章</span>
            <span v-if="topic.status === 'coming'" class="topic-card__badge">即将推出</span>
          </div>
          <h3 class="topic-card__title">{{ topic.title }}</h3>
          <p class="topic-card__desc">{{ topic.description }}</p>
          <span v-if="topic.status !== 'coming'" class="topic-card__cta">进入主题 →</span>
        </component>
      </div>
    </div>
  </section>
</template>
