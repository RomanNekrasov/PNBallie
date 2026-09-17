<template>
  <router-view v-slot="{ Component, route: viewRoute }">
    <component :is="Component" :key="`${viewRoute.path}:${['/verify-email', '/reset-password'].includes(viewRoute.path) ? 0 : currentGroup?.id ?? 0}`" />
  </router-view>
</template>

<script setup lang="ts">
import { watch, watchEffect } from 'vue'
import { useTableSettings } from './composables/useTableSettings'
import { tableVariables } from './tableSettings'
import { useRoute, useRouter } from 'vue-router'
import { authUser, currentGroup } from './auth'
import { trackScreen, type AnalyticsScreen } from './analytics'

const router = useRouter()
const route = useRoute()
const { tableSettings } = useTableSettings()
watchEffect(() => {
  for (const [key, value] of Object.entries(tableVariables(tableSettings.value))) document.documentElement.style.setProperty(key, value)
})
watch(() => route.path, path => {
  const screen: AnalyticsScreen | undefined = ({ '/': 'game', '/profile': 'profile', '/groups': 'groups', '/admin': 'admin', '/login': 'login' } as Record<string, AnalyticsScreen>)[path]
  if (screen) trackScreen(screen)
  else if (path.startsWith('/join/')) trackScreen('groups')
}, { immediate: true })
watch(authUser, user => {
  if (!user && route.meta.requiresAuth) void router.replace({ path: '/login', query: { redirect: route.fullPath } })
})
</script>
