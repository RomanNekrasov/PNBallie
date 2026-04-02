import { ref } from 'vue'
import type { Player } from '../types'
import { api } from './useApi'

const players = ref<Player[]>([])
const loading = ref(false)

export function usePlayers() {
  async function fetchPlayers() {
    loading.value = true
    try {
      players.value = await api<Player[]>('/api/players')
    } finally {
      loading.value = false
    }
  }

  async function deletePlayer(id: number) {
    await api('/api/players/' + id, { method: 'DELETE' })
    players.value = players.value.filter(p => p.id !== id)
  }

  return { players, loading, fetchPlayers, deletePlayer }
}
