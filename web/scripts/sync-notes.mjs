/**
 * 1) 将 notes/<主题>/notes/ 同步到 web/docs/<主题>/notes/
 * 2) 按各主题 notes 下 .md 数量生成 topic-stats.generated.ts（首页章数自动）
 */
import {
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const repoRoot = join(__dirname, '../..')
const notesRoot = join(repoRoot, 'notes')
const docsRoot = join(__dirname, '../docs')
const statsFile = join(__dirname, '../docs/.vitepress/topic-stats.generated.ts')

function listTopics() {
  if (!existsSync(notesRoot)) return []
  return readdirSync(notesRoot).filter((name) => {
    if (name.startsWith('.')) return false
    const chapterNotes = join(notesRoot, name, 'notes')
    return existsSync(chapterNotes) && statSync(chapterNotes).isDirectory()
  })
}

function countChapters(topic) {
  const dir = join(notesRoot, topic, 'notes')
  return readdirSync(dir).filter((f) => f.endsWith('.md') && !f.startsWith('.')).length
}

function syncTopic(topic) {
  const src = join(notesRoot, topic, 'notes')
  const dest = join(docsRoot, topic, 'notes')
  mkdirSync(join(docsRoot, topic), { recursive: true })
  if (existsSync(dest)) {
    rmSync(dest, { recursive: true, force: true })
  }
  cpSync(src, dest, { recursive: true })
  console.log(`synced: notes/${topic}/notes -> docs/${topic}/notes`)
}

const topics = listTopics()
const stats = {}
for (const topic of topics) {
  syncTopic(topic)
  stats[topic] = countChapters(topic)
}

const body = `/** 由 web/scripts/sync-notes.mjs 自动生成，勿手改 */
export default ${JSON.stringify(stats, null, 2)} as Record<string, number>
`
writeFileSync(statsFile, body, 'utf8')
console.log(`stats: ${statsFile} -> ${JSON.stringify(stats)}`)
