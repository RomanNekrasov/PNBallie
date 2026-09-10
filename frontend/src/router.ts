import { createRouter, createWebHistory } from 'vue-router'
import { authUser, currentGroup, isGroupAdmin } from './auth'
import GameView from './views/GameView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: () => import('./views/LoginView.vue') },
    { path: '/groups', component: () => import('./views/GroupsView.vue'), meta: { requiresAuth: true } },
    { path: '/join/:code', component: () => import('./views/GroupsView.vue'), meta: { requiresAuth: true } },
    { path: '/', component: GameView, meta: { requiresAuth: true, requiresGroup: true } },
    { path: '/stats', component: () => import('./views/StatsView.vue'), meta: { requiresAuth: true, requiresGroup: true } },
    { path: '/profile', component: () => import('./views/ProfileView.vue'), meta: { requiresAuth: true, requiresGroup: true } },
    { path: '/admin', component: () => import('./views/AdminView.vue'), meta: { requiresAuth: true, requiresGroup: true, requiresAdmin: true } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(to => {
  if (to.meta.requiresAuth && !authUser.value) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.meta.requiresGroup && !currentGroup.value) return '/groups'
  if (to.meta.requiresAdmin && !isGroupAdmin.value) return '/'
})
export default router
