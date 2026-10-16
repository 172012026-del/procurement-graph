<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
const props = defineProps({ modelValue: { type: Array, default: () => [] }, options: { type: Array, default: () => [] }, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
const open = ref(false), search = ref(''), root = ref(null), trigger = ref(null), input = ref(null)
const filtered = computed(() => props.options.filter(x => x.toLowerCase().includes(search.value.trim().toLowerCase())))
const visible = computed(() => filtered.value.slice(0, 40))
async function toggle() { open.value = !open.value; if (open.value) { await nextTick(); input.value?.focus() } }
function close() { open.value = false; trigger.value?.focus() }
function change(name) { emit('update:modelValue', props.modelValue.includes(name) ? props.modelValue.filter(x => x !== name) : [...props.modelValue, name]) }
function outside(event) { if (!root.value?.contains(event.target)) open.value = false }
onMounted(() => document.addEventListener('pointerdown', outside))
onBeforeUnmount(() => document.removeEventListener('pointerdown', outside))
</script>

<template>
  <div ref="root" class="supplier-picker" @keydown.esc.stop.prevent="close">
    <button ref="trigger" type="button" class="select-trigger" :disabled="disabled" :aria-expanded="open" aria-controls="supplier-options" @click="toggle">
      <span>{{ modelValue.length ? `已选择 ${modelValue.length} 家供应商` : '选择至少两家供应商' }}</span><span aria-hidden="true">⌄</span>
    </button>
    <div v-if="open" id="supplier-options" class="picker-popover">
      <input ref="input" v-model="search" type="search" placeholder="输入供应商名称" aria-label="搜索供应商" autocomplete="off">
      <div class="picker-options" role="group" aria-label="供应商候选项">
        <label v-for="name in visible" :key="name" class="checkbox-option"><input type="checkbox" :checked="modelValue.includes(name)" :disabled="!modelValue.includes(name) && modelValue.length >= 30" @change="change(name)"><span>{{ name }}</span></label>
        <p v-if="!visible.length" class="muted picker-empty">没有匹配的供应商</p>
      </div>
      <div class="picker-footer"><span>{{ filtered.length }} 家匹配{{ filtered.length > 40 ? '，请搜索缩小范围' : '' }}</span><button type="button" class="text-button" @click="close">完成选择</button></div>
    </div>
    <div v-if="modelValue.length" class="selected-suppliers" aria-label="已选供应商">
      <button v-for="name in modelValue" :key="name" type="button" class="selection-chip" :disabled="disabled" :aria-label="`移除${name}`" @click="change(name)">{{ name }} <span aria-hidden="true">×</span></button>
    </div>
  </div>
</template>
