<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
const props = defineProps({ open: Boolean, title: String, wide: Boolean })
const emit = defineEmits(['close'])
const dialog = ref(null)
watch(() => props.open, async value => {
  await nextTick()
  if (value && !dialog.value.open) dialog.value.showModal()
  else if (!value && dialog.value.open) dialog.value.close()
}, { immediate: true })
onBeforeUnmount(() => dialog.value?.close())
function close() { emit('close') }
function backdrop(event) {
  if (event.target !== dialog.value) return
  const rect = dialog.value.getBoundingClientRect()
  if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) close()
}
</script>

<template>
  <Teleport to="body">
    <dialog ref="dialog" class="side-panel" :class="{ wide }" :aria-label="title" @cancel.prevent="close" @click="backdrop">
      <div class="panel-header"><h2>{{ title }}</h2><button class="button small" aria-label="关闭侧栏" autofocus @click="close">关闭 <span aria-hidden="true">×</span></button></div>
      <div class="panel-body"><slot></slot></div>
    </dialog>
  </Teleport>
</template>
