<template>
  <div>
    <section class="stats-row" v-if="overview">
      <div class="card stat" v-for="s in statCards" :key="s.label">
        <div class="num" :class="s.cls">{{ s.value }}</div>
        <div class="label">{{ s.label }}</div>
      </div>
      <div class="gen meta">数据更新于 {{ overview.generatedAt }}</div>
    </section>

    <section class="entries">
      <div class="card entry" @click="$emit('go', 'tree')">
        <div class="tag">脉络 ①</div>
        <h2>主题知识树</h2>
        <p>按技术主题从属与学习先后关系组织：7 个阶段（打地基 → 认格局 → 造与跑 → 会干活 → 扩感官 → 稳落地 → 追前沿），节点内含子主题与代表文章。</p>
        <div class="hint">适合系统学习与按主题检索</div>
      </div>
      <div class="card entry" @click="$emit('go', 'flow')">
        <div class="tag">脉络 ②</div>
        <h2>时间线 × 应用分类</h2>
        <p>十一条应用知识脉络多栏并列（编程、具身智能、算法优化、内容创作、科研、办公、消费产品、行业、算力、安全、日常新闻），每列内按时间演进、月份为时间刻度；文章按主分类归列，日常新闻为兜底分类、置于最底部。</p>
        <div class="hint">支持搜索与价值分筛选 · 适合跟进展、找应用切入点</div>
      </div>
    </section>

    <section v-if="overview">
      <h2 class="sec-title">⑂ GitHub 可复现项目精选 <span class="meta">（全部 {{ overview.totals.withGithub }} 篇见各脉络视图与 kb/项目库/GitHub速查.md）</span></h2>
      <div class="gh-grid">
        <div class="card gh-card" v-for="a in overview.topGithub.slice(0, 12)" :key="a.uid">
          <div class="gh-title">
            <a v-if="a.path" href="#" @click.prevent="$emit('open', a)">{{ a.title }}</a>
            <span v-else>{{ a.title }}</span>
          </div>
          <a class="gh-link" :href="a.github[0]" target="_blank" rel="noreferrer">{{ a.github[0] }}</a>
          <div class="meta" style="margin-top:6px">
            <span class="badge b-score5" v-if="a.score >= 5">{{ a.score }}分</span>
            <span class="badge b-score4" v-else-if="a.score === 4">{{ a.score }}分</span>
            <span class="badge b-type">{{ TYPE_CN[a.type] || a.type }}</span>{{ a.date }} · {{ a.source }}
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { TYPE_CN } from '../constants.js'
const props = defineProps({ overview: Object })
defineEmits(['go', 'open'])

const statCards = computed(() => {
  const t = props.overview?.totals || {}
  return [
    { label: '文章总量', value: t.articles ?? '-' },
    { label: '已分类', value: t.classified ?? '-' },
    { label: '高价值 ≥4 分', value: t.highScore ?? '-', cls: 'hi' },
    { label: '带 GitHub 仓库', value: t.withGithub ?? '-', cls: 'gh' },
    { label: '应用脉络覆盖', value: t.tagCoverage ?? '-' },
    { label: '有全文', value: t.withFulltext ?? '-' },
    { label: '机器之心', value: t.bySource?.['机器之心'] ?? '-' },
    { label: '新智元', value: t.bySource?.['新智元'] ?? '-' }
  ]
})
</script>

<style scoped>
.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 10px; position: relative; }
.stat { padding: 14px 16px; text-align: center; }
.stat .num { font-size: 24px; font-weight: 700; }
.stat .num.gh { color: #57d36f; }
.stat .num.hi { color: var(--accent); }
.stat .label { color: var(--muted); font-size: 12px; margin-top: 4px; }
.gen { grid-column: 1 / -1; text-align: right; margin: -4px 2px 0 0; }
.entries { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 26px; }
.entry { padding: 20px 22px; cursor: pointer; transition: border-color .15s; }
.entry:hover { border-color: var(--accent); }
.entry .tag { color: var(--accent); font-size: 12px; margin-bottom: 6px; }
.entry p { color: var(--muted); font-size: 13px; line-height: 1.7; margin: 10px 0; }
.entry .hint { font-size: 12px; color: var(--accent); }
.sec-title { margin: 18px 0 12px; font-size: 17px; }
.gh-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.gh-card { padding: 12px 14px; }
.gh-title { font-size: 13px; font-weight: 600; margin-bottom: 6px; max-height: 40px; overflow: hidden; }
@media (max-width: 900px) { .stats-row { grid-template-columns: repeat(2, 1fr); } .entries, .gh-grid { grid-template-columns: 1fr; } }
</style>
