<template>
  <div v-if="apptree">
    <div class="toolbar">
      <div class="btn" :class="{ active: mode === 'timeline' }" @click="mode = 'timeline'">时间线进度（多脉络并列）</div>
      <div class="btn" :class="{ active: mode === 'apps' }" @click="mode = 'apps'">应用分类</div>
      <label style="margin-left:14px"><input type="checkbox" v-model="onlyGh" /> 只看带 GitHub 仓库的项目</label>
      <input class="search" v-model="q" placeholder="搜索标题 / 摘要…" />
      <select class="sel" v-model.number="minScore" title="按价值分筛选">
        <option :value="0">全部价值分</option>
        <option :value="4">≥4 分</option>
        <option :value="5">仅 5 分</option>
      </select>
      <span class="meta">每列 = 一条应用知识脉络，文章按加权主分类归列（不跨列重复），列内按时间倒序、月份为时间刻度</span>
    </div>

    <!-- 时间线进度：按应用脉络多栏并列 -->
    <div v-if="mode === 'timeline'" class="kanban">
      <div class="card col" v-for="c in columns" :key="c.id">
        <div class="col-head">
          <b>{{ c.name }}</b>
          <span class="meta">{{ c.arts.length }} 篇 · ⑂ {{ c.ghCount }} 带仓库</span>
        </div>
        <div class="col-desc">{{ c.desc }}</div>
        <div class="col-body">
          <template v-for="(item, i) in visible(c)" :key="i">
            <div class="m-chip" v-if="item.month">{{ item.month }}</div>
            <ArticleCard v-else :a="item" compact @open="$emit('open', $event)" />
          </template>
          <div v-if="c.arts.length > PREVIEW" style="margin:6px 0">
            <div class="btn" style="font-size:12px" @click="toggle(c.id)">
              {{ expanded.has(c.id) ? '收起' : `展开其余 ${c.arts.length - PREVIEW} 篇` }}
            </div>
          </div>
          <div class="meta" v-if="!c.arts.length" style="padding:4px 2px">暂无匹配文章</div>
        </div>
      </div>
    </div>

    <!-- 应用分类 -->
    <div v-else>
      <div class="apps-overview">
        <div class="card app-card" v-for="c in apptree" :key="c.id" :class="{ active: current?.id === c.id }" @click="current = c">
          <b>{{ c.name }}</b>
          <div class="d">{{ c.desc }}</div>
          <div class="c">{{ c.count }} 篇 · ⑂ {{ c.articles.filter(a => a.github.length).length }} 带仓库</div>
        </div>
      </div>
      <div class="card panel" v-if="current">
        <h3>{{ current.name }} <span class="meta">{{ current.count }} 篇{{ onlyGh ? '（仅显示带仓库）' : '' }}</span></h3>
        <p class="meta">{{ current.desc }}</p>
        <ArticleCard v-for="a in currentArticles" :key="a.uid" :a="a" @open="$emit('open', $event)" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import ArticleCard from './ArticleCard.vue'

const props = defineProps({ apptree: Object, articles: Array })
defineEmits(['open'])
const mode = ref('timeline')
const onlyGh = ref(false)
const expanded = ref(new Set())
const current = ref(null)
const q = ref('')
const minScore = ref(0)
const PREVIEW = 12

const kwMatch = (a) => {
  const kw = q.value.trim().toLowerCase()
  if (!kw) return true
  return (a.title || '').toLowerCase().includes(kw) || (a.takeaway || '').toLowerCase().includes(kw)
}

const filtered = computed(() => {
  let list = props.articles
  if (onlyGh.value) list = list.filter((a) => a.github.length)
  if (minScore.value) list = list.filter((a) => a.score >= minScore.value)
  return list.filter(kwMatch)
})

// 多栏并列：每个应用分类一条脉络列（顺序 = app-tree.yaml 书写顺序）；未命中标签的进「待归类」列
const columns = computed(() => {
  const cols = props.apptree.map((a) => ({ id: a.id, name: a.name, desc: a.desc, arts: [] }))
  const byId = Object.fromEntries(cols.map((c) => [c.id, c]))
  const other = { id: '__other', name: '待归类', desc: '暂未归入应用分类的文章', arts: [] }
  for (const a of filtered.value) {
    if (!a.apps || !a.apps.length) { other.arts.push(a); continue }
    const id = a.apps[0] // 首标签 = 加权得分最高的主分类：一篇只归一列，不跨列重复
    byId[id] && byId[id].arts.push(a)
  }
  cols.push(other)
  for (const c of cols) {
    c.arts.sort((a, b) => (b.date || '').localeCompare(a.date || '') || b.score - a.score)
    c.ghCount = c.arts.filter((a) => a.github.length).length
  }
  return cols
})

// 列内插入月份刻度
function visible(c) {
  const base = expanded.value.has(c.id) ? c.arts : c.arts.slice(0, PREVIEW)
  const out = []
  let cur = ''
  for (const a of base) {
    const m = (a.date || '').slice(0, 7)
    if (m && m !== cur) { out.push({ month: m }); cur = m }
    out.push(a)
  }
  return out
}
const toggle = (id) => { const s = new Set(expanded.value); s.has(id) ? s.delete(id) : s.add(id); expanded.value = s }

// 面板直接用快照（价值分降序→日期降序的前 12 条），不再从全量数组按日期重捞覆盖顺序
const currentArticles = computed(() => {
  if (!current.value) return []
  let list = current.value.articles
  if (onlyGh.value) list = list.filter((a) => a.github.length)
  if (minScore.value) list = list.filter((a) => a.score >= minScore.value)
  return list.filter(kwMatch)
})
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
.search { padding: 4px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); color: var(--text); font-size: 13px; width: 190px; }
.sel { padding: 4px 8px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); color: var(--text); font-size: 13px; }
.kanban { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; align-items: start; }
.col { padding: 0; overflow: hidden; }
.col-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; padding: 10px 12px 4px; }
.col-head b { font-size: 14px; }
.col-desc { padding: 0 12px 8px; color: var(--muted); font-size: 11px; border-bottom: 1px solid var(--line); }
.col-body { padding: 6px 10px 10px; max-height: 66vh; overflow-y: auto; }
.m-chip { display: inline-block; background: var(--panel2); color: var(--accent); border: 1px solid var(--line); border-radius: 10px; padding: 1px 10px; font-size: 11px; margin: 8px 0 2px; }
.apps-overview { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 18px; }
.app-card { padding: 14px 16px; cursor: pointer; }
.app-card:hover, .app-card.active { border-color: var(--accent); }
.app-card .d { color: var(--muted); font-size: 12px; margin: 5px 0; }
.app-card .c { font-size: 12px; color: var(--accent); }
.panel { padding: 16px 18px; }
@media (max-width: 1200px) { .kanban { grid-template-columns: repeat(2, 1fr); } .apps-overview { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 700px) { .kanban, .apps-overview { grid-template-columns: 1fr; } }
</style>
