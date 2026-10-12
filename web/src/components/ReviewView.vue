<template>
  <div class="review">
    <!-- 左列：待归类 + 已锁定的审阅队列 -->
    <div class="card queue">
      <div class="q-head">
        <b>审阅队列</b>
        <span class="meta">{{ filtered.length }} 篇待处理 · 已锁定 {{ lockedCount }} 篇</span>
      </div>
      <div class="q-tools">
        <input class="search" v-model="q" placeholder="搜索标题 / 摘要…" />
        <label class="lk-toggle"><input type="checkbox" v-model="showLocked" /> 已锁定</label>
      </div>
      <div class="q-list">
        <div v-for="a in filtered" :key="a.uid" class="q-item" :class="{ sel: sel && sel.uid === a.uid }" @click="pick(a)">
          <span v-if="a.locked" class="lock" title="人工锁定：机器重分类不会覆盖">🔒</span>
          <span class="q-title">{{ a.title }}</span>
          <span class="meta">{{ a.date }} · {{ a.source }}</span>
        </div>
        <div v-if="!filtered.length" class="meta" style="padding:12px">队列已清空，全部文章均已归类。</div>
      </div>
    </div>

    <!-- 右侧：打标编辑器 -->
    <div class="card editor">
      <template v-if="sel">
        <div class="e-title">{{ sel.title }}</div>
        <div class="meta">{{ sel.date }} · {{ sel.source }} · {{ sel.url }}</div>
        <div class="takeaway" v-if="sel.takeaway">{{ sel.takeaway }}</div>
        <div class="e-actions">
          <a v-if="sel.path" href="#" @click.prevent="$emit('open', sel)">查看全文 ↗</a>
          <a v-for="g in sel.github" :key="g" :href="g" target="_blank" rel="noreferrer">⑂ {{ g }}</a>
        </div>

        <div class="hint">点选应用分类，<b>点选顺序即优先级</b>，第 1 个为主分类（决定归列）；最多 3 个。保存后人工标签锁定，机器重分类不会覆盖。</div>
        <div class="chips">
          <div v-for="d in domains" :key="d.id" class="chip" :class="{ on: order(d.id) > 0 }"
               :title="d.desc" @click="toggle(d.id)">
            <span v-if="order(d.id)" class="ord">{{ order(d.id) }}</span>{{ d.name }}
            <span v-if="order(d.id) === 1" class="primary">主分类</span>
          </div>
        </div>

        <div class="msg" :class="{ err: errMsg }" v-if="msg">{{ msg }}</div>

        <div class="btns">
          <button class="btn save" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
          <button class="btn" :disabled="saving" @click="reset">取消</button>
          <button v-if="sel.locked" class="btn unlock" :disabled="saving" @click="unlock">解锁（清标签回待归类）</button>
        </div>

        <div class="preview">
          <div class="p-head">正文预览 <span class="meta">{{ hasFulltext ? '· 本地全文' : '· 该文章暂无本地全文，请点上方原文链接阅读' }}</span></div>
          <div class="p-body" v-html="previewHtml"></div>
        </div>
      </template>
      <div v-else class="meta" style="padding:20px">← 从左侧队列选择一篇文章开始打标。</div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { marked } from 'marked'
import { api } from '../api'

const props = defineProps({ apptree: Array, articles: Array })
const emit = defineEmits(['open', 'saved'])

const q = ref('')
const sel = ref(null)
const picked = ref([])        // 点选顺序的 id 数组，[0] 即主分类
const saving = ref(false)
const msg = ref('')
const errMsg = ref(false)
const previewHtml = ref('')
const hasFulltext = ref(false)
const showLocked = ref(false) // 已锁定(已处理)文章默认不进队列：处理一个移走一个

const domains = computed(() => props.apptree || [])
const pendingCount = computed(() => (props.articles || []).filter((a) => !a.apps?.length && !a.locked).length)
const lockedCount = computed(() => (props.articles || []).filter((a) => a.locked).length)
const queue = computed(() => (props.articles || []).filter((a) => a.locked ? showLocked.value : !a.apps?.length))
const filtered = computed(() => {
  const kw = q.value.trim().toLowerCase()
  if (!kw) return queue.value
  return queue.value.filter((a) =>
    (a.title || '').toLowerCase().includes(kw) || (a.takeaway || '').toLowerCase().includes(kw))
})

const order = (id) => picked.value.indexOf(id) + 1
function toggle(id) {
  const i = picked.value.indexOf(id)
  if (i >= 0) picked.value.splice(i, 1)
  else if (picked.value.length < 3) picked.value.push(id)
}
function pick(a) {
  sel.value = a
  picked.value = [...(a.apps || [])]
  msg.value = ''
  errMsg.value = false
}
function reset() {
  if (sel.value) picked.value = [...(sel.value.apps || [])]
  msg.value = ''
  errMsg.value = false
}
async function save() {
  if (!sel.value || !picked.value.length) return
  saving.value = true
  msg.value = ''
  try {
    await api.saveReview({ uid: sel.value.uid, apps: [...picked.value], lock: true })
    msg.value = `已保存并锁定：${picked.value.length} 个标签（主分类：${picked.value[0]}）。`
    emit('saved')
  } catch (e) {
    errMsg.value = true
    msg.value = `保存失败：${e.message}`
  } finally {
    saving.value = false
  }
}
async function unlock() {
  if (!sel.value || !confirm(`解锁「${sel.value.title.slice(0, 30)}…」？将清空人工标签、回到待归类，机器可重新打标。`)) return
  saving.value = true
  msg.value = ''
  try {
    await api.saveReview({ uid: sel.value.uid, apps: [], lock: false })
    msg.value = '已解锁，文章回到待归类。'
    emit('saved')
    sel.value = null
    picked.value = []
  } catch (e) {
    errMsg.value = true
    msg.value = `解锁失败：${e.message}`
  } finally {
    saving.value = false
  }
}
// 选中文章后加载正文预览（与全文抽屉同一渲染管线）；令牌防快速切换时的过期响应
watch(sel, async (a) => {
  previewHtml.value = ''
  hasFulltext.value = false
  if (!a) return
  const token = a.uid
  if (a.path) {
    try {
      const md = await api.article(a.path)
      if (sel.value && sel.value.uid !== token) return
      hasFulltext.value = true
      previewHtml.value = marked.parse((md || '').replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, '') || '（无全文）')
    } catch {
      previewHtml.value = '<p>全文加载失败，请点上方原文链接。</p>'
    }
  } else {
    previewHtml.value = ''
  }
})
// 数据刷新后（保存/解锁成功），同步队列里的最新状态
watch(() => props.articles, () => {
  if (!sel.value) return
  const fresh = (props.articles || []).find((a) => a.uid === sel.value.uid)
  sel.value = fresh || null
  picked.value = fresh ? [...(fresh.apps || [])] : []
})
</script>

<style scoped>
.review { display: flex; gap: 16px; align-items: flex-start; }
.queue { width: 380px; flex: none; display: flex; flex-direction: column; max-height: calc(100vh - 120px); }
.q-head { display: flex; justify-content: space-between; align-items: baseline; padding: 12px 14px 6px; }
.q-tools { display: flex; align-items: center; gap: 8px; margin: 4px 12px 8px; }
.q-tools .search { margin: 0; flex: 1; min-width: 0; }
.lk-toggle { font-size: 12px; color: var(--muted); white-space: nowrap; cursor: pointer; }
.q-list { overflow-y: auto; padding: 0 8px 10px; }
.q-item { display: flex; flex-direction: column; padding: 8px 10px; border-radius: 8px; cursor: pointer; }
.q-item:hover { background: var(--hover, #f2f4f8); }
.q-item.sel { background: var(--sel, #e8eeff); }
.q-title { font-size: 13px; font-weight: 600; line-height: 1.5; }
.lock { float: right; margin-left: 6px; }
.editor { flex: 1; padding: 18px 20px; position: sticky; top: 76px; max-height: calc(100vh - 96px); overflow-y: auto; }
.preview { margin-top: 18px; border-top: 1px solid var(--line); }
.p-head { padding: 12px 0 6px; font-size: 13px; font-weight: 700; }
.p-body { font-size: 13px; line-height: 1.8; }
.p-body :deep(h1), .p-body :deep(h2), .p-body :deep(h3) { margin: 16px 0 8px; font-size: 15px; }
.p-body :deep(p) { line-height: 1.85; font-size: 13px; color: #d7dbe8; margin: 8px 0; }
.p-body :deep(img) { max-width: 100%; border-radius: 8px; }
.p-body :deep(pre) { background: #0c0f1a; padding: 12px; border-radius: 8px; overflow-x: auto; font-size: 12px; }
.p-body :deep(code) { color: #9ecbff; }
.p-body :deep(a) { color: #7fa4ff; word-break: break-all; }
.e-title { font-size: 17px; font-weight: 700; line-height: 1.5; }
.e-actions { margin-top: 8px; display: flex; flex-direction: column; gap: 3px; font-size: 12px; }
.e-actions a { color: #0b7a3b; word-break: break-all; }
.hint { margin: 16px 0 8px; font-size: 12px; color: var(--muted); line-height: 1.6; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { border: 1px solid var(--line); border-radius: 999px; padding: 5px 13px; font-size: 13px; cursor: pointer; user-select: none; display: flex; align-items: center; gap: 6px; }
.chip:hover { border-color: #5b7cfa; }
.chip.on { background: #e8eeff; border-color: #2f5fe0; color: #1f3f9e; font-weight: 600; }
.ord { background: #2f5fe0; color: #fff; border-radius: 50%; width: 17px; height: 17px; font-size: 11px; display: inline-flex; align-items: center; justify-content: center; }
.primary { font-size: 11px; color: #b45309; font-weight: 700; }
.btns { margin-top: 18px; display: flex; gap: 10px; }
.btn.save { background: #2f5fe0; color: #fff; }
.btn.save:disabled { opacity: .6; }
.btn.unlock { color: #b45309; }
.msg { margin-top: 12px; font-size: 13px; color: #0b7a3b; }
.msg.err { color: #c0392b; }
.takeaway { margin-top: 8px; color: var(--muted); font-size: 13px; line-height: 1.7; }
</style>
