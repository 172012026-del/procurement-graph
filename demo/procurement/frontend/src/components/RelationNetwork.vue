<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { useWorkspace } from '../composables/useWorkspace'
import EmptyState from './EmptyState.vue'
const w = useWorkspace(), element = ref(null), limit = ref(8), loading = ref(false), error = ref(''), summary = ref('')
let chart, observer, token = 0, disposed = false
const types = ['purchaser', 'project', 'supplier'], colors = ['#3567b2', '#9b7949', '#578879']
async function draw() {
  const sequence = ++token, dataset = w.dataset
  loading.value = true; error.value = ''; summary.value = ''; chart?.dispose(); chart = null
  try {
    const [data, { engine }] = await Promise.all([api.graph({ dataset_id: dataset, limit: limit.value }), import('../graph')])
    if (disposed || sequence !== token || w.dataset !== dataset) return
    loading.value = false
    await nextTick()
    if (disposed || sequence !== token || !element.value) return
    summary.value = `${data.nodes.length} 个主体 · ${data.links.length} 条关系`
    chart = engine.init(element.value, null, { renderer: 'canvas' })
    chart.setOption({ animation: false, tooltip: { renderMode: 'richText', confine: true, formatter: params => params.dataType === 'edge' ? params.data.relation : params.data.name }, series: [{ type: 'graph', layout: 'force', roam: true, draggable: true, force: { repulsion: 170, edgeLength: [65, 120], gravity: 0.12, layoutAnimation: false }, data: data.nodes.map(node => ({ ...node, category: types.indexOf(node.type), itemStyle: { color: colors[types.indexOf(node.type)] || colors[2] }, symbolSize: node.type === 'purchaser' ? 24 : node.type === 'project' ? 16 : 10, label: { show: node.type === 'purchaser', color: '#334155', fontSize: 12, position: 'bottom', width: 140, overflow: 'truncate' } })), links: data.links, lineStyle: { color: '#c5cdd6', width: 1, opacity: 0.65 }, emphasis: { focus: 'adjacency', label: { show: true, backgroundColor: '#fff', padding: 5, width: 200, overflow: 'break', color: '#172235' }, lineStyle: { width: 2, opacity: 1 } } }] })
    chart.on('click', params => { if (params.dataType === 'node' && params.data.type === 'project') { const id = Number(String(params.data.id).replace('project:', '')); if (Number.isFinite(id)) w.openProject(id) } })
    chart.resize()
  } catch (cause) { if (sequence === token && !disposed) { error.value = cause.message; loading.value = false } }
}
watch(() => [w.dataset, limit.value], draw)
onMounted(() => { observer = new ResizeObserver(() => chart?.resize()); observer.observe(element.value); draw() })
onBeforeUnmount(() => { disposed = true; ++token; observer?.disconnect(); chart?.dispose() })
</script>

<template>
  <section class="surface network-surface" aria-label="关系网络">
    <div class="section-heading"><div><h2>关系网络</h2><p>拖动与缩放查看联系，悬停读取名称，点击采购包打开详情。</p></div><label class="chart-select">采购包数 <select v-model.number="limit" aria-label="关系网络采购包数"><option v-for="value in [8, 16, 30, 80]" :key="value" :value="value">{{ value }}</option></select></label></div>
    <div class="network-legend"><span><i :style="{ background: colors[0] }"></i>采购单位</span><span><i :style="{ background: colors[1] }"></i>采购包</span><span><i :style="{ background: colors[2] }"></i>供应商</span><span class="muted" data-testid="network-summary">{{ summary }}</span></div>
    <div v-if="error" class="notice danger inset" role="alert">{{ error }}<button class="text-button" @click="draw">重新加载</button></div>
    <EmptyState v-if="loading" busy title="正在绘制关系网络"></EmptyState>
    <div ref="element" class="network-canvas" :class="{ 'is-hidden': loading || error }" aria-label="可拖动的采购关系网络"></div>
    <p class="footnote network-note">为保持可读性，仅显示所选数量的采购包。完整关系请使用上方查询表格。</p>
  </section>
</template>
