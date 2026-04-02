import { createRouter, createWebHistory } from 'vue-router'
import { getActiveAccount, login } from './auth'
import GameView from './views/GameView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: GameView, meta: { requiresAuth: true } },
    { path: '/stats', component: () => import('./views/StatsView.vue'), meta: { requiresAuth: true } },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.requiresAuth) {
    const account = getActiveAccount()
    if (!account) {
      await login()
      return false
    }
  }
})

export default router
