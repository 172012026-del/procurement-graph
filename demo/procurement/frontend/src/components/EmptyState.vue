<script setup>
defineProps({ title: { type: String, default: '暂无结果' }, description: String, busy: Boolean })
</script>

<template>
  <div class="empty-state" :aria-busy="busy">
    <span v-if="busy" class="spinner" aria-hidden="true"></span>
    <h3>{{ title }}</h3>
    <p v-if="description">{{ description }}</p>
    <slot></slot>
  </div>
</template>
