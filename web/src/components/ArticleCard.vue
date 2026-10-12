<template>
  <div class="card art" :class="{ compact }">
    <div class="t">
      <a v-if="a.path" href="#" @click.prevent="$emit('open', a)">{{ a.title }}</a>
      <span v-else>{{ a.title }}</span>
      <a v-if="a.path && !compact" class="raw" :href="a.path" target="_blank" title="打开 markdown 原文">md</a>
    </div>
    <div class="meta">
      <span class="badge" :class="scoreCls" v-if="a.score">{{ a.score }}分</span>
      <span class="badge b-type" v-if="TYPE_CN[a.type] && TYPE_CN[a.type] !== '待整理'">{{ TYPE_CN[a.type] }}</span>
      <span class="badge b-type" v-else-if="!a.score" title="类型/价值分待「更新知识库」整理会话判定；应用分类已由脚本打好">待整理</span>
      {{ a.date }} · {{ a.source }}
      <span v-if="a.locked" title="人工锁定：机器重分类不会覆盖"> · 🔒</span>
      <span v-if="names.length"> · {{ names.join('/') }}</span>
    </div>
    <div class="takeaway" v-if="!compact && a.takeaway">{{ a.takeaway }}</div>
    <div class="gh" v-if="a.github.length">
      <a v-for="g in a.github" :key="g" class="gh-link" :href="g" target="_blank" rel="noreferrer">{{ g }}</a>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { TYPE_CN, appNames } from '../constants'

const props = defineProps({ a: Object, compact: Boolean })
defineEmits(['open'])
const scoreCls = computed(() => (props.a.score >= 5 ? 'b-score5' : props.a.score >= 4 ? 'b-score4' : 'b-score3'))
const names = computed(() => appNames(props.a.apps))
</script>

<style scoped>
.art { padding: 10px 14px; margin: 8px 0; }
.art.compact { padding: 7px 10px; margin: 6px 0; }
.t { font-size: 14px; font-weight: 600; }
.compact .t { font-size: 13px; }
.t .raw { font-size: 11px; margin-left: 8px; color: var(--muted); font-weight: 400; }
.takeaway { color: var(--muted); font-size: 12px; margin-top: 4px; line-height: 1.6; }
.gh { margin-top: 5px; display: flex; flex-direction: column; }
</style>
