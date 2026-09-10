import { ref, watch } from 'vue'
import { api } from './useApi'
import { currentGroup } from '../auth'
import type { StatsMode, StatsPeriod, StatsResponse } from '../types'

export function useStats() {
  const stats = ref<StatsResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const mode = ref<StatsMode>('all')
  const period = ref<StatsPeriod>('all')
  let requestId = 0

  watch(() => currentGroup.value?.id, () => {
    requestId++
    stats.value = null
    loading.value = false
    error.value = null
  }, { flush: 'sync' })

  async function fetchStats() {
    const request = ++requestId
    loading.value = true
    error.value = null
    try {
      const query = new URLSearchParams({ mode: mode.value, period: period.value })
      const response = await api<StatsResponse>(`/api/stats?${query}`)
      if (request === requestId) stats.value = response
    } catch (e: any) {
      if (request === requestId) error.value = e.message || 'Statistieken laden is niet gelukt'
    } finally {
      if (request === requestId) loading.value = false
    }
  }

  return { stats, loading, error, mode, period, fetchStats }
}
