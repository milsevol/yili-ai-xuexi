/**
 * 将各主题 notes/ 同步到 web/docs/<主题>/notes/，供 VitePress 渲染。
 * 源文件仍以仓库根下「主题/notes」为准。
 */
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const repoRoot = join(__dirname, '../..')
const docsRoot = join(__dirname, '../docs')

const SKIP = new Set(['web', 'node_modules', '.git', '.github'])

function listTopics() {
  return readdirSync(repoRoot).filter((name) => {
    if (SKIP.has(name) || name.startsWith('.')) return false
    const notes = join(repoRoot, name, 'notes')
    return existsSync(notes) && statSync(notes).isDirectory()
  })
}

function syncTopic(topic) {
  const src = join(repoRoot, topic, 'notes')
  const dest = join(docsRoot, topic, 'notes')
  mkdirSync(join(docsRoot, topic), { recursive: true })
  if (existsSync(dest)) {
    rmSync(dest, { recursive: true, force: true })
  }
  cpSync(src, dest, { recursive: true })
  console.log(`synced: ${topic}/notes -> docs/${topic}/notes`)
}

for (const topic of listTopics()) {
  syncTopic(topic)
}
