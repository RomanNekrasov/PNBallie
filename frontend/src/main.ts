import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import { initAuth } from './auth'
import { ensureLoggedInPlayerExists } from './playerProvisioning'

await initAuth()
try {
  await ensureLoggedInPlayerExists()
} catch (error) {
  console.error('Failed to provision player for logged-in account', error)
}

createApp(App).use(router).mount('#app')
