<template>
  <teleport to="body">
    <div class="mask" v-if="article" @click.self="$emit('close')">
      <div class="drawer card">
        <div class="head">
          <div>
            <h3>{{ article.title }}</h3>
            <div class="meta">
              <span class="badge" :class="article.score >= 4 ? 'b-score4' : 'b-score3'">{{ article.score }}分</span>
              <span class="badge b-type">{{ article.type }}</span>
              {{ article.date }} · {{ article.source }}
              <a :href="article.url" target="_blank" rel="noreferrer">原文 ↗</a>
              <a v-for="g in article.github" :key="g" class="gh-link" :href="g" target="_blank" rel="noreferrer" style="margin-left:10px">{{ g }}</a>
            </div>
          </div>
          <span class="close" @click="$emit('close')">✕</span>
        </div>
        <div class="body" v-html="html"></div>
      </div>
    </div>
  </teleport>
</template>

<script setup>
import { marked } from 'marked'
import { ref, watch } from 'vue'
import { api } from '../api'

const props = defineProps({ article: Object })
defineEmits(['close'])
const html = ref('')

watch(() => props.article, async (a) => {
  html.value = ''
  if (a && a.path) {
    const md = await api.article(a.path)
    html.value = marked.parse(md || '（无全文）')
  } else if (a) {
    html.value = '<p>该文章暂无本地全文（pending_content），请通过「原文」链接访问。</p>'
  }
})
</script>

<style scoped>
.mask { position: fixed; inset: 0; background: rgba(0, 0, 0, .5); z-index: 50; display: flex; justify-content: flex-end; }
.drawer { width: 640px; max-width: 96vw; height: 100%; border-radius: 0; overflow-y: auto; padding: 20px 24px; }
.head { display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--line); padding-bottom: 12px; margin-bottom: 14px; }
.close { cursor: pointer; color: var(--muted); font-size: 16px; }
.body :deep(h1), .body :deep(h2), .body :deep(h3) { margin: 18px 0 8px; }
.body :deep(p) { line-height: 1.85; font-size: 14px; color: #d7dbe8; }
.body :deep(img) { max-width: 100%; border-radius: 8px; }
.body :deep(pre) { background: #0c0f1a; padding: 12px; border-radius: 8px; overflow-x: auto; font-size: 12px; }
.body :deep(code) { color: #9ecbff; }
</style>
