<script setup>
import { computed } from 'vue'
import { useWorkspace } from '../composables/useWorkspace'
import { money } from '../utils/presentation'
import EmptyState from './EmptyState.vue'

const w = useWorkspace()
const report = computed(() => w.projectDetail?.item_hierarchy)
const nodes = computed(() => Object.fromEntries((report.value?.nodes || []).map(node => [node.key, node])))
const item = key => nodes.value[key]?.item || {}
function showSource(key) {
  const value = item(key)
  w.evidence = { ...value, winner_supplier: value.supplier, project_name: w.projectDetail.name, lot_name: w.projectDetail.lot_name }
}
</script>

<template>
  <section class="hierarchy-view" aria-label="摘要与明细核验">
    <template v-if="report">
      <dl class="hierarchy-counts">
        <div><dt>原文记录</dt><dd>{{ report.summary.source_count }}</dd></div>
        <div><dt>明细视图</dt><dd>{{ report.summary.detail_count }}</dd></div>
        <div><dt>待核验关联</dt><dd>{{ report.summary.review_groups }}</dd></div>
      </dl>
      <p class="footnote">原文记录完整保留。只有范围、行号、供应商和金额等检查全部通过，明细视图才折叠摘要；未确认的关联保留全部行。</p>
      <EmptyState v-if="!report.relations.length" title="暂未发现可核验的摘要与明细关联" description="原文记录继续使用。缺少明确文件引用或行级证据时，不自动折叠。" />
      <article v-for="relation in report.relations" :key="relation.parent" class="hierarchy-group" :data-hierarchy-status="relation.status">
        <header class="hierarchy-heading">
          <div><span class="cell-note">{{ relation.status === 'confirmed' ? '已核验摘要' : '待核验摘要' }}</span><strong>{{ item(relation.parent).product_name || '未命名摘要' }}</strong></div>
          <span class="status" :class="relation.status === 'confirmed' ? 'success' : 'warning'">{{ relation.status === 'confirmed' ? '包含关系已确认' : '保留全部原文行' }}</span>
        </header>
        <div class="hierarchy-source"><span>{{ item(relation.parent).source_file }}</span><span>{{ money(item(relation.parent).total_price) }}</span><button class="text-button" @click="showSource(relation.parent)">查看摘要原文</button></div>
        <ul class="hierarchy-children">
          <li v-for="key in relation.children" :key="key"><div><strong>{{ item(key).product_name || '未命名明细' }}</strong><span class="cell-note">{{ item(key).business_line_id }} · {{ item(key).source_file }}</span></div><span class="hierarchy-amount">{{ money(item(key).total_price) }}</span><button class="text-button" @click="showSource(key)">查看明细原文</button></li>
        </ul>
        <details class="hierarchy-checks"><summary>核验依据 · {{ relation.checks.filter(check => check.passed).length }}/{{ relation.checks.length }} 项通过</summary><ul><li v-for="check in relation.checks" :key="check.code"><span :class="{ 'check-pending': !check.passed }">{{ check.passed ? '通过' : '待核验' }}</span>{{ check.description }}</li></ul></details>
      </article>
      <p v-if="report.summary.unknown_amount_count" class="footnote">明细视图仍有 {{ report.summary.unknown_amount_count }} 条记录未披露总价，不能把已知金额之和视为完整成交额。</p>
      <div class="hierarchy-export"><button class="button secondary" :disabled="w.exporting" @click="w.download('detail')">下载当前数据集的明细三表</button><span class="footnote">表头保持比赛格式；未确认的关联保留原文行。</span></div>
    </template>
    <EmptyState v-else title="层级核验暂不可用" />
  </section>
</template>

<style scoped>
.hierarchy-view { padding-top: 18px; }
.hierarchy-counts { display: flex; gap: 32px; margin: 0 0 12px; }
.hierarchy-counts dt { font-size: 12px; color: var(--muted); }
.hierarchy-counts dd { margin: 2px 0 0; font-size: 22px; font-variant-numeric: tabular-nums; }
.hierarchy-group { padding: 20px 0; border-top: 1px solid var(--line); }
.hierarchy-heading, .hierarchy-source, .hierarchy-children li { display: flex; align-items: center; gap: 14px; }
.hierarchy-heading { justify-content: space-between; flex-wrap: wrap; }
.hierarchy-source { margin: 8px 0 14px; flex-wrap: wrap; font-size: 12px; color: var(--muted); overflow-wrap: anywhere; }
.hierarchy-children { margin: 0 0 14px 5px; padding: 0 0 0 18px; border-left: 2px solid var(--line); list-style: none; }
.hierarchy-children li { padding: 9px 0; flex-wrap: wrap; }
.hierarchy-children li > div { flex: 1; min-width: 150px; overflow-wrap: anywhere; }
.hierarchy-children strong { font-size: 13px; font-weight: 500; }
.hierarchy-amount { font-variant-numeric: tabular-nums; font-size: 12px; }
.hierarchy-checks { font-size: 12px; }
.hierarchy-checks summary { cursor: pointer; color: var(--muted); padding: 5px 0; }
.hierarchy-checks ul { list-style: none; padding: 8px 0; margin: 0; }
.hierarchy-checks li { display: flex; gap: 12px; margin: 5px 0; }
.hierarchy-checks li > span { color: #34816b; flex-shrink: 0; }
.hierarchy-checks li > .check-pending { color: #94682e; }
.hierarchy-export { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
@media (max-width: 480px) { .hierarchy-counts { gap: 22px; } .hierarchy-heading .status { font-size: 11px; } }
</style>
