<script setup>
import dashboard from '../assets/icons/layout-dashboard.svg?raw'
import files from '../assets/icons/file-import.svg?raw'
import search from '../assets/icons/database-search.svg?raw'
import relations from '../assets/icons/affiliate.svg?raw'
import settings from '../assets/icons/settings-2.svg?raw'
import magnify from '../assets/icons/search.svg?raw'
import upload from '../assets/icons/upload.svg?raw'
import help from '../assets/icons/help-circle.svg?raw'
defineProps({ name: String })
const icons = { dashboard, files, search, relations, settings, magnify, upload, help }
</script>

<template><span class="app-icon" aria-hidden="true" v-html="icons[name] || ''"></span></template>
