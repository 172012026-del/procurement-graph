<script setup>
import { computed } from 'vue'
const props = defineProps({ total: { type: Number, default: 0 }, page: { type: Number, default: 1 }, pageSize: { type: Number, default: 20 }, busy: Boolean, sizes: Array, label: { type: String, default: '记录' } })
const emit = defineEmits(['change', 'size'])
const count = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const start = computed(() => props.total ? (props.page - 1) * props.pageSize + 1 : 0)
</script>

<template>
  <nav class="pagination" :aria-label="`${label}分页`">
    <span class="pagination-summary">{{ start }}–{{ Math.min(page * pageSize, total) }} / {{ total.toLocaleString('zh-CN') }} 条</span>
    <div class="pagination-controls">
      <label v-if="sizes" class="page-size">每页 <select :value="pageSize" :disabled="busy" :aria-label="`${label}每页条数`" @change="emit('size', Number($event.target.value))"><option v-for="size in sizes" :key="size" :value="size">{{ size }}</option></select></label>
      <button class="button small" :disabled="page <= 1 || busy" :aria-label="`${label}上一页`" @click="emit('change', page - 1)">上一页</button>
      <span class="page-index">{{ page }} / {{ count }}</span>
      <button class="button small" :disabled="page >= count || busy" :aria-label="`${label}下一页`" @click="emit('change', page + 1)">下一页</button>
    </div>
  </nav>
</template>
