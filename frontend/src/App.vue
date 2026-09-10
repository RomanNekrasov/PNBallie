<template>
  <router-view v-slot="{ Component, route: viewRoute }">
    <component :is="Component" :key="`${viewRoute.path}:${currentGroup?.id ?? 0}`" />
  </router-view>
</template>

<script setup lang="ts">
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authUser, currentGroup } from './auth'
import { trackScreen, type AnalyticsScreen } from './analytics'

const router = useRouter()
const route = useRoute()
watch(() => route.path, path => {
  const screen: AnalyticsScreen | undefined = ({ '/': 'game', '/profile': 'profile', '/groups': 'groups', '/admin': 'admin', '/login': 'login' } as Record<string, AnalyticsScreen>)[path]
  if (screen) trackScreen(screen)
  else if (path.startsWith('/join/')) trackScreen('groups')
}, { immediate: true })
watch(authUser, user => {
  if (!user && route.meta.requiresAuth) void router.replace({ path: '/login', query: { redirect: route.fullPath } })
})
</script>
