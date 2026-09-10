import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import { initAuth } from './auth'
import { initAnalytics } from './analytics'

try {
  await initAuth()
  void initAnalytics()
  createApp(App).use(router).mount('#app')
} catch (error) {
  console.error('Applicatie kon niet starten', error)
  const root = document.querySelector<HTMLDivElement>('#app')
  if (root) {
    root.innerHTML = '<main style="padding:2rem"><h1>PNBallie</h1><p role="alert">De app kan niet verbinden. Controleer je verbinding en probeer het opnieuw.</p><button onclick="location.reload()">Opnieuw proberen</button></main>'
  }
}
