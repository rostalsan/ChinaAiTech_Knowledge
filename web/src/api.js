const j = (url) => fetch(url).then((r) => r.json())

const post = (url, body) => fetch(url, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body)
}).then(async (r) => {
  const data = await r.json()
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`)
  return data
})

export const api = {
  overview: () => j('/api/overview'),
  articles: () => j('/api/articles'),
  topics: () => j('/api/topics'),
  apptree: () => j('/api/apptree'),
  article: (p) => fetch('/api/article?path=' + encodeURIComponent(p)).then((r) => r.text()),
  // 人工审阅打标：{ uid, apps: [id≤3，点选顺序即优先级], lock }；apps 空 + lock false = 解锁
  saveReview: (payload) => post('/api/review', payload)
}
