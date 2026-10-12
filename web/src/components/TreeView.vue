<template>
  <div class="wrap" v-if="topics">
    <div class="toolbar">
      <label><input type="checkbox" v-model="onlyGh" /> 只看带 GitHub 仓库的项目</label>
      <input class="search" v-model="q" placeholder="搜索节点 / 标题 / 摘要…" />
      <select class="sel" v-model.number="minScore" title="按价值分筛选面板文章">
        <option :value="0">全部价值分</option>
        <option :value="4">≥4 分</option>
        <option :value="5">仅 5 分</option>
      </select>
      <span class="meta">阶段自上而下即建议学习顺序（先后关系只标注在此处）；点节点卡片查看子主题与文章（从属关系）</span>
    </div>
    <div class="rail" v-if="topics">
      <div class="lane" v-for="grp in stages" :key="grp.stage">
        <div class="lane-dot"></div>
        <h2>第 {{ grp.stage }} 阶段 · {{ topics.stages[grp.stage] }}</h2>
        <div class="nodes">
          <div class="card node" v-for="n in grp.nodes" :key="n.id" :class="{ active: current?.id === n.id }" @click="current = n">
            <b>{{ n.name }}</b>
            <div class="d">{{ n.desc }}</div>
            <div class="c">{{ n.count }} 篇 · ⑂ {{ ghCount(n) }} 带仓库</div>
            <div class="req" v-if="n.requires.length">前置：{{ reqCn(n.requires) }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="panel" v-if="current">
      <div class="p-head">
        <h3>{{ current.name }} <span class="meta">{{ current.count }} 篇</span></h3>
        <span class="close" @click="current = null">✕</span>
      </div>
      <p class="meta">{{ current.desc }}</p>
      <b class="sub-t">子主题（从属）</b>
      <ul class="subs"><li v-for="s in current.subtopics" :key="s">{{ s }}</li></ul>
      <b class="sub-t">文章（按价值分{{ onlyGh ? '，仅显示带仓库' : '' }}）</b>
      <ArticleCard v-for="a in shownArticles" :key="a.uid" :a="a" @open="$emit('open', $event)" />
    </div>
    <div class="panel-mask" v-if="current" @click="current = null"></div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import ArticleCard from './ArticleCard.vue'

const props = defineProps({ topics: Object })
defineEmits(['open'])
const current = ref(null)
const onlyGh = ref(false)
const q = ref('')
const minScore = ref(0)

const nameById = computed(() => Object.fromEntries((props.topics?.nodes || []).map((n) => [n.id, n.name])))
const reqCn = (requires) => requires.map((r) => nameById.value[r] || r).join('、')

const kwMatch = (a) => {
  const kw = q.value.trim().toLowerCase()
  if (!kw) return true
  return (a.title || '').toLowerCase().includes(kw) || (a.takeaway || '').toLowerCase().includes(kw)
}
const nodeVisible = (n) => {
  const kw = q.value.trim().toLowerCase()
  if (!kw) return true
  const self = (n.name + ' ' + n.desc + ' ' + (n.subtopics || []).join(' ')).toLowerCase().includes(kw)
  return self || n.articles.some(kwMatch)
}

const stages = computed(() => {
  if (!props.topics) return []
  const map = new Map()
  for (const n of props.topics.nodes) {
    if (!nodeVisible(n)) continue
    if (!map.has(n.stage)) map.set(n.stage, [])
    map.get(n.stage).push(n)
  }
  return [...map.entries()].map(([stage, nodes]) => ({ stage, nodes })).sort((a, b) => a.stage - b.stage)
})

const ghCount = (n) => n.articles.filter((a) => a.github.length).length
const shownArticles = computed(() => {
  if (!current.value) return []
  let list = current.value.articles
  if (onlyGh.value) list = list.filter((a) => a.github.length)
  if (minScore.value) list = list.filter((a) => a.score >= minScore.value)
  return list.filter(kwMatch)
})
</script>

<style scoped>
.toolbar { display: flex; align-items: center; gap: 16px; margin-bottom: 14px; flex-wrap: wrap; }
.toolbar label { cursor: pointer; font-size: 13px; }
.search { padding: 4px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); color: var(--text); font-size: 13px; width: 190px; }
.sel { padding: 4px 8px; border: 1px solid var(--line); border-radius: 8px; background: var(--panel); color: var(--text); font-size: 13px; }
.rail { position: relative; padding-left: 22px; }
.rail::before { content: ""; position: absolute; left: 5px; top: 8px; bottom: 8px; width: 2px; background: var(--line); }
.lane { position: relative; padding: 6px 0 14px; }
.lane-dot { position: absolute; left: -22px; top: 14px; width: 12px; height: 12px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 3px rgba(91, 140, 255, .2); }
.lane h2 { font-size: 16px; }
.nodes { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; }
.node { flex: 1 1 300px; max-width: 560px; padding: 13px 16px; cursor: pointer; }
.node:hover, .node.active { border-color: var(--accent); }
.node .d { color: var(--muted); font-size: 12px; margin: 5px 0; line-height: 1.55; }
.node .c { font-size: 12px; color: var(--accent); }
.node .req { font-size: 11px; color: var(--muted); margin-top: 5px; }
.panel { position: fixed; top: 0; right: 0; width: 470px; max-width: 94vw; height: 100vh; overflow-y: auto; background: var(--panel); border-left: 1px solid var(--line); padding: 18px 20px; z-index: 30; }
.panel-mask { position: fixed; inset: 0; background: rgba(0, 0, 0, .35); z-index: 25; }
.p-head { display: flex; justify-content: space-between; align-items: center; }
.close { cursor: pointer; color: var(--muted); }
.sub-t { display: block; font-size: 13px; margin: 14px 0 6px; color: var(--text); }
.subs { margin: 0; padding-left: 18px; color: var(--muted); font-size: 12px; line-height: 1.9; }
</style>
