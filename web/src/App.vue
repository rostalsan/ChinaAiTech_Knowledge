<template>
  <div class="shell">
    <header class="top">
      <div class="brand" @click="view = 'home'">AI 知识库 <span class="sub">机器之心 × 新智元</span></div>
      <nav>
        <button class="btn" :class="{ active: view === 'home' }" @click="view = 'home'">首页</button>
        <button class="btn" :class="{ active: view === 'tree' }" @click="view = 'tree'">脉络① 主题知识树</button>
        <button class="btn" :class="{ active: view === 'flow' }" @click="view = 'flow'">脉络② 时间线 × 应用</button>
        <button class="btn" :class="{ active: view === 'review' }" @click="view = 'review'">人工审阅</button>
      </nav>
      <a class="gh-note" href="https://github.com/rostalsan/ChinaAiTech_Knowledge" target="_blank" rel="noopener" title="本项目已开源（MIT），去 GitHub 点个 Star">⑂ 项目开源·GitHub</a>
      <span class="author-note" :title="copied ? '已复制，去微信搜索关注' : '点击复制公众号名'" @click="copyGzh">作者·坤叔 ｜ 关注公众号「坤叔的AI炼金房」{{ copied ? ' ✓已复制' : '' }}</span>
      <div class="stats" v-if="overview">
        <span>{{ overview.totals.articles }} 篇</span>
        <span class="gh-num">⑂ {{ overview.totals.withGithub }} 带 GitHub</span>
      </div>
    </header>
    <main>
      <HomeView v-if="view === 'home'" :overview="overview" @go="view = $event" @open="openArticle" />
      <TreeView v-else-if="view === 'tree'" :topics="topics" @open="openArticle" />
      <FlowView v-else-if="view === 'flow'" :apptree="apptree" :articles="articles" @open="openArticle" />
      <ReviewView v-else-if="view === 'review'" :apptree="apptree" :articles="articles" @open="openArticle" @saved="refresh" />
    </main>
    <ArticleDrawer :article="current" @close="current = null" />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { api } from './api'
import HomeView from './components/HomeView.vue'
import TreeView from './components/TreeView.vue'
import FlowView from './components/FlowView.vue'
import ReviewView from './components/ReviewView.vue'
import ArticleDrawer from './components/ArticleDrawer.vue'

const view = ref('home')
const copied = ref(false)
const copyGzh = async () => {
  try { await navigator.clipboard.writeText('坤叔的AI炼金房') } catch { /* 剪贴板不可用时仅作提示 */ }
  copied.value = true
  setTimeout(() => (copied.value = false), 1600)
}
const overview = ref(null)
const topics = ref(null)
const apptree = ref(null)
const articles = ref([])
const current = ref(null)

function openArticle(a) { current.value = a }

async function refresh() {
  // 人工打标入库并刷新快照后，重拉看板数据
  overview.value = await api.overview()
  apptree.value = await api.apptree()
  articles.value = await api.articles()
}

onMounted(async () => {
  overview.value = await api.overview()
  topics.value = await api.topics()
  apptree.value = await api.apptree()
  articles.value = await api.articles()
})
</script>

<style scoped>
.shell { min-height: 100vh; }
.top { display: flex; align-items: center; gap: 18px; padding: 12px 26px; background: var(--panel); border-bottom: 1px solid var(--line); position: sticky; top: 0; z-index: 10; }
.brand { font-size: 17px; font-weight: 700; cursor: pointer; }
.brand .sub { font-size: 12px; color: var(--muted); font-weight: 400; margin-left: 8px; }
.author-note { white-space: nowrap; font-size: 12.5px; color: var(--gold); border: 1px solid rgba(232, 185, 63, .45); background: rgba(232, 185, 63, .08); border-radius: 999px; padding: 4px 12px; cursor: pointer; user-select: none; }
.author-note:hover { background: rgba(232, 185, 63, .18); }
.gh-note { white-space: nowrap; font-size: 12.5px; color: #57d36f; border: 1px solid rgba(87, 211, 111, .45); background: rgba(87, 211, 111, .08); border-radius: 999px; padding: 4px 12px; }
.gh-note:hover { background: rgba(87, 211, 111, .18); text-decoration: none; }
nav { display: flex; gap: 8px; flex: 1; }
.stats { display: flex; gap: 14px; color: var(--muted); font-size: 13px; }
.gh-num { color: #57d36f; }
main { padding: 20px 30px; max-width: 1680px; margin: 0 auto; width: 100%; }
</style>
