import express from 'express'
import fs from 'node:fs'
import path from 'node:path'
import { execFile } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const DATA_DIR = path.join(__dirname, 'data')
const FULLTEXT_DIR = path.join(__dirname, '..', '..', 'data', 'fulltext')
const DIST_DIR = path.join(__dirname, '..', 'dist')
const ROOT_DIR = path.join(__dirname, '..', '..')
const QUEUE_FILE = path.join(ROOT_DIR, 'data', 'queue', 'manual_tags.jsonl')
const PORT = process.env.PORT || 8787

const app = express()
app.use(express.json())

// 数据文件每次请求时读取：Python 侧 build/export 后无需重启即可生效
const readData = (name) => JSON.parse(fs.readFileSync(path.join(DATA_DIR, name), 'utf-8'))
const send = (res, name) => {
  try { res.json(readData(name)) } catch { res.status(500).json({ error: `数据文件缺失：${name}，请先运行 python scripts/export_web.py` }) }
}

app.get('/api/overview', (req, res) => send(res, 'overview.json'))
app.get('/api/articles', (req, res) => send(res, 'articles.json'))
app.get('/api/topics', (req, res) => send(res, 'topics.json'))
app.get('/api/apptree', (req, res) => send(res, 'apptree.json'))

// 全文 markdown：仅允许 data/fulltext 白名单前缀，防目录穿越
app.get('/api/article', (req, res) => {
  const p = String(req.query.path || '')
  if (!p.startsWith('/fulltext/')) return res.status(400).json({ error: 'bad path' })
  const fp = path.normalize(path.join(FULLTEXT_DIR, p.slice('/fulltext/'.length)))
  if (!fp.startsWith(FULLTEXT_DIR) || !fs.existsSync(fp)) return res.status(404).json({ error: 'not found' })
  res.type('text/plain; charset=utf-8').send(fs.readFileSync(fp, 'utf-8'))
})

// 人工审阅打标（Node 不直连 SQLite）：校验后追加队列行，调 Python 入库并刷新快照
app.post('/api/review', (req, res) => {
  const { uid, apps, lock } = req.body || {}
  if (!uid || typeof uid !== 'string') return res.status(400).json({ error: '缺少 uid' })
  if (!Array.isArray(apps) || apps.length > 3 || apps.some((a) => typeof a !== 'string'))
    return res.status(400).json({ error: 'apps 须为字符串数组且最多 3 个' })
  let validIds
  try {
    validIds = new Set(readData('apptree.json').map((a) => a.id))
  } catch {
    return res.status(500).json({ error: 'apptree.json 缺失，请先运行 python scripts/export_web.py' })
  }
  const bad = apps.filter((a) => !validIds.has(a))
  if (bad.length) return res.status(400).json({ error: `未知应用分类：${bad.join(', ')}` })
  const line = JSON.stringify({ uid, apps, lock: lock ? 1 : 0, ts: new Date().toISOString() })
  fs.mkdirSync(path.dirname(QUEUE_FILE), { recursive: true })
  fs.appendFileSync(QUEUE_FILE, line + '\n')
  const py = process.env.PYTHON || 'python'
  execFile(py, [path.join(ROOT_DIR, 'scripts', 'ingest_manual_tags.py')],
    { cwd: ROOT_DIR, timeout: 120000, maxBuffer: 10 * 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) {
        console.error('[review] ingest failed:', stderr || err.message)
        return res.status(500).json({ error: `入库脚本失败：${String(stderr || err.message).slice(0, 200)}` })
      }
      console.log(`[review] ${uid} -> [${apps.join(', ')}] lock=${lock ? 1 : 0}`)
      res.json({ ok: true, uid, apps, lock: lock ? 1 : 0, ingest: stdout.trim().slice(-400) })
    })
})

// 生产态：vite build 产物 + 全文静态 + SPA 回退
if (fs.existsSync(path.join(DIST_DIR, 'index.html'))) {
  app.use(express.static(DIST_DIR))
  app.use('/fulltext', express.static(FULLTEXT_DIR))
  app.get(/^\/(?!api|fulltext).*/, (req, res) => res.sendFile(path.join(DIST_DIR, 'index.html')))
} else {
  app.get('/', (req, res) => res.type('text/plain; charset=utf-8').send(
    '前端尚未构建：请先 npm run build（或开发模式 npm run dev，走 5173 端口）'))
}

app.listen(PORT, () => console.log(`[ai-kb server] http://localhost:${PORT}  (data: ${DATA_DIR})`))
