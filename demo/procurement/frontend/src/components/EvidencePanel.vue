<script setup>
import { computed } from 'vue'
import { useWorkspace } from '../composables/useWorkspace'
import { jsonValue, money, number } from '../utils/presentation'
import SidePanel from './SidePanel.vue'
const w = useWorkspace()
const related = computed(() => jsonValue(w.evidence?.related_sources, []))
const derived = computed(() => jsonValue(w.evidence?.derived_values, {}))
</script>

<template>
  <SidePanel :open="!!w.evidence" title="标的来源" @close="w.evidence = null">
    <template v-if="w.evidence">
      <p class="eyebrow">{{ w.evidence.category || '未披露品目' }}</p>
      <h3 class="detail-title">{{ w.evidence.product_name || '未命名标的' }}</h3>
      <p class="muted">{{ w.evidence.project_name }}<span v-if="w.evidence.lot_name"> · {{ w.evidence.lot_name }}</span></p>
      <dl class="detail-fields">
        <div><dt>品牌</dt><dd>{{ w.evidence.brand || '未披露' }}</dd></div><div><dt>规格型号</dt><dd>{{ w.evidence.model || '未披露' }}</dd></div>
        <div><dt>单价</dt><dd>{{ money(w.evidence.unit_price) }}</dd></div><div><dt>数量</dt><dd>{{ w.evidence.quantity == null ? '未披露' : number(w.evidence.quantity) }} {{ w.evidence.quantity_unit }}</dd></div>
        <div><dt>总价</dt><dd>{{ money(w.evidence.total_price) }}</dd></div><div><dt>中标供应商</dt><dd>{{ w.evidence.winner_supplier || '未披露' }}</dd></div>
      </dl>
      <section class="detail-section"><h3>原文证据</h3><blockquote class="source-quote">{{ w.evidence.evidence || '这条记录暂未保存原文片段，请查看来源文件。' }}</blockquote></section>
      <section v-if="w.evidence.source_context?.text" class="detail-section"><h3>程序定位的原文行</h3><blockquote class="source-quote grounded-quote">{{ w.evidence.source_context.text }}</blockquote><p class="footnote">{{ w.evidence.source_context.location }}</p></section>
      <dl class="source-fields"><div><dt>来源文件</dt><dd>{{ w.evidence.source_file || '未记录' }}</dd></div><div><dt>定位</dt><dd>{{ w.evidence.source_location || w.evidence.line_id || '未记录' }}</dd></div><div v-if="w.evidence.business_line_id"><dt>原文业务行</dt><dd>{{ w.evidence.business_line_id }}</dd></div><div><dt>来源类型</dt><dd>{{ w.evidence.source === 'announcement' ? '公告正文' : w.evidence.source === 'attachment' ? '采购附件' : w.evidence.source || '未记录' }}</dd></div></dl>
      <section v-if="related.length" class="detail-section"><h3>其他关联来源</h3><pre class="code-content">{{ JSON.stringify(related, null, 2) }}</pre></section>
      <section v-if="Object.keys(derived).length" class="detail-section"><h3>计算与补充说明</h3><pre class="code-content">{{ JSON.stringify(derived, null, 2) }}</pre></section>
      <p class="footnote">未披露的字段保留为空，不把缺失金额当作零。来源片段用于核对，不能替代原始公告。</p>
    </template>
  </SidePanel>
</template>
