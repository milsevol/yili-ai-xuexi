/**
 * 将 notes/<主题>/notes/ 同步到 web/docs/<主题>/notes/，供 VitePress 渲染。
 * 学习内容统一放在仓库根目录 notes/ 下。
 */
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const repoRoot = join(__dirname, '../..')
const notesRoot = join(repoRoot, 'notes')
const docsRoot = join(__dirname, '../docs')

function listTopics() {
  if (!existsSync(notesRoot)) return []
  return readdirSync(notesRoot).filter((name) => {
    if (name.startsWith('.')) return false
    const chapterNotes = join(notesRoot, name, 'notes')
    return existsSync(chapterNotes) && statSync(chapterNotes).isDirectory()
  })
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

for (const topic of listTopics()) {
  syncTopic(topic)
}
