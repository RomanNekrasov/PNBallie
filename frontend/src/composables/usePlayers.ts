import { ref, watch } from 'vue'
import { currentGroup } from '../auth'
import type { Player } from '../types'
import { api } from './useApi'

const players = ref<Player[]>([])
const loading = ref(false)
let requestId = 0
watch(() => currentGroup.value?.id, () => {
  players.value = []
  loading.value = false
  requestId++
}, { flush: 'sync' })

export function usePlayers() {
  async function fetchPlayers() {
    const request = ++requestId
    loading.value = true
    try {
      const result = await api<Player[]>('/api/players')
      if (request === requestId) players.value = result
    } finally {
      if (request === requestId) loading.value = false
    }
  }

  async function deletePlayer(id: number) {
    await api('/api/players/' + id, { method: 'DELETE' })
    players.value = players.value.filter(p => p.id !== id)
  }

  return { players, loading, fetchPlayers, deletePlayer }
}
