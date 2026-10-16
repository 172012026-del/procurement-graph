import { createApp } from 'vue'
import App from './App.vue'
import { tabIndicator } from './directives/tabIndicator'
import './workspace.css'
import './theme.css'

createApp(App).directive('tab-indicator', tabIndicator).mount('#app')

