import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import { initAuth } from './auth'
import { ensureLoggedInPlayerExists } from './playerProvisioning'

try {
  await initAuth()
  await ensureLoggedInPlayerExists()
  createApp(App).use(router).mount('#app')
} catch (error) {
  console.error('Applicatie kon niet starten', error)
  const root = document.querySelector<HTMLDivElement>('#app')
  if (root) {
    root.innerHTML = '<p role="alert">De applicatie kan niet starten. Controleer de configuratie en probeer het opnieuw.</p>'
  }
}
