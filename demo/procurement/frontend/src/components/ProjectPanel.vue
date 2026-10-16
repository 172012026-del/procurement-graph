<script setup>
import { computed } from 'vue'
import { useWorkspace } from '../composables/useWorkspace'
import { money, number, statusName, statusTone } from '../utils/presentation'
import SidePanel from './SidePanel.vue'
import EmptyState from './EmptyState.vue'
import ItemHierarchy from './ItemHierarchy.vue'
const w = useWorkspace()
const warnings = computed(() => (w.projectDetail?.warnings || '').split(' | ').filter(Boolean))
const winners = computed(() => w.projectDetail?.winners || [...new Set((w.projectDetail?.bids || [])
  .filter(bid => bid.is_winner === 1 || bid.is_winner === true)
  .map(bid => bid.bidder || bid.bidder_name).filter(Boolean))].join('、'))
</script>

<template>
  <SidePanel :open="w.projectPanelOpen" title="采购包详情" wide @close="w.closeProject">
    <EmptyState v-if="w.projectDetailLoading" busy title="正在读取采购包"></EmptyState>
    <div v-else-if="w.projectDetailError" class="notice danger" role="alert">{{ w.projectDetailError }}</div>
    <template v-else-if="w.projectDetail">
      <div class="detail-kicker"><span class="status" :class="statusTone(w.projectDetail.processing_status)">{{ statusName(w.projectDetail.processing_status) }}</span><span class="muted">{{ w.projectDetail.announcement_date || '日期未披露' }}</span></div>
      <h3 class="detail-title">{{ w.projectDetail.name }}</h3><p class="muted">{{ w.projectDetail.lot_name }}</p>
      <dl class="detail-fields"><div><dt>采购单位</dt><dd>{{ w.projectDetail.purchaser || '未披露' }}</dd></div><div><dt>项目编号</dt><dd>{{ w.projectDetail.project_code || '未披露' }}</dd></div><div><dt>中标供应商</dt><dd>{{ winners || '未披露' }}</dd></div><div><dt>中标金额</dt><dd class="amount-emphasis">{{ money(w.projectDetail.awarded_amount) }}</dd></div></dl>
      <div class="segmented" aria-label="详情内容"><button :class="{ active: w.projectDetailTab === 'items' }" :aria-pressed="w.projectDetailTab === 'items'" @click="w.projectDetailTab = 'items'">标的明细 <span>{{ w.projectDetail.items?.length || 0 }}</span></button><button :class="{ active: w.projectDetailTab === 'bids' }" :aria-pressed="w.projectDetailTab === 'bids'" @click="w.projectDetailTab = 'bids'">竞标结果 <span>{{ w.projectDetail.bids?.length || 0 }}</span></button><button :class="{ active: w.projectDetailTab === 'hierarchy' }" :aria-pressed="w.projectDetailTab === 'hierarchy'" @click="w.projectDetailTab = 'hierarchy'">层级核验</button></div>
      <div v-if="w.projectDetailTab === 'items'" class="table-scroll detail-table"><table><thead><tr><th>标的 / 品牌型号</th><th class="numeric">数量</th><th class="numeric">单价</th><th class="numeric">总价</th><th>核对</th></tr></thead><tbody><tr v-for="item in w.projectDetail.items" :key="item.id"><td><strong class="cell-title">{{ item.product_name || '未披露' }}</strong><span class="cell-note">{{ [item.brand, item.model].filter(Boolean).join(' · ') || '品牌型号未披露' }}</span></td><td class="numeric">{{ item.quantity == null ? '未披露' : number(item.quantity) }} {{ item.quantity_unit }}</td><td class="numeric">{{ money(item.unit_price) }}</td><td class="numeric">{{ money(item.total_price) }}</td><td><button class="text-button" @click="w.evidence = { ...item, project_name: w.projectDetail.name, lot_name: w.projectDetail.lot_name }">来源</button></td></tr></tbody></table><EmptyState v-if="!w.projectDetail.items?.length" title="暂未提取标的明细"></EmptyState></div>
      <div v-else-if="w.projectDetailTab === 'bids'" class="table-scroll detail-table"><table><thead><tr><th>投标主体</th><th>审查状态</th><th class="numeric">投标金额</th><th class="numeric">得分 / 排名</th><th>结果</th></tr></thead><tbody><tr v-for="bid in w.projectDetail.bids" :key="bid.id"><td class="entity-cell">{{ bid.bidder_name || bid.bidder }}</td><td><span>{{ bid.review_status || '未披露' }}</span><span class="cell-note" v-if="bid.eligible === 0 || bid.eligible === false">不计入有效共同竞标</span></td><td class="numeric">{{ money(bid.bid_amount) }}</td><td class="numeric">{{ bid.score == null ? '未披露' : number(bid.score) }} / {{ bid.rank ?? '未披露' }}</td><td><span v-if="bid.is_winner" class="status success">中标</span><span v-else class="muted">未中标</span></td></tr></tbody></table><EmptyState v-if="!w.projectDetail.bids?.length" title="暂未提取投标记录"></EmptyState></div>
      <ItemHierarchy v-else />
      <section v-if="warnings.length" class="detail-section"><h3>处理说明 <span class="muted">{{ warnings.length }} 项</span></h3><ul class="explanation-list"><li v-for="warning in warnings" :key="warning">{{ warning }}</li></ul></section>
      <div class="source-footer"><span class="muted">{{ w.projectDetail.notice_uuid }}</span><a v-if="w.projectDetail.source_url?.startsWith('https://')" class="text-button" :href="w.projectDetail.source_url" target="_blank" rel="noopener noreferrer">打开原始公告 ↗</a></div>
    </template>
  </SidePanel>
</template>
