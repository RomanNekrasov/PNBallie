import { ref } from 'vue'
import { api } from './useApi'
import type { StatsResponse } from '../types'

export function useStats() {
  const stats = ref<StatsResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function fetchStats() {
    loading.value = true
    error.value = null
    try {
      stats.value = await api<StatsResponse>('/api/stats')
    } catch (e: any) {
      error.value = e.message || 'Failed to load stats'
    } finally {
      loading.value = false
    }
  }

  return { stats, loading, error, fetchStats }
}
