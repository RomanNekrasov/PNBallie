import { ref, computed } from 'vue'
import type { Match, MatchCreate, MatchPlayerEntry, Position } from '../types'
import { api } from './useApi'

export function useMatch() {
  const orangeScore = ref(10)
  const blueScore = ref(10)
  const selectedPlayers = ref<Record<Position, number | null>>({
    orange_front: null,
    orange_back: null,
    blue_front: null,
    blue_back: null,
  })
  const submitting = ref(false)
  const feedback = ref<string | null>(null)
  const sessionMatches = ref<Match[]>([])
  const sessionStart = ref<number | null>(null)
  const SESSION_MAX_MS = 30 * 60 * 1000

  function resetScores() {
    orangeScore.value = 10
    blueScore.value = 10
  }

  const sessionExpired = computed(() =>
    sessionStart.value !== null && Date.now() - sessionStart.value > SESSION_MAX_MS
  )

  const canSubmit = computed(() => {
    const orangeCount = [selectedPlayers.value.orange_front, selectedPlayers.value.orange_back].filter(id => id !== null).length
    const blueCount = [selectedPlayers.value.blue_front, selectedPlayers.value.blue_back].filter(id => id !== null).length
    const teamsEqual = orangeCount > 0 && blueCount > 0 && orangeCount === blueCount
    const oneIsTen = orangeScore.value === 10 || blueScore.value === 10
    const notEqual = orangeScore.value !== blueScore.value
    return teamsEqual && oneIsTen && notEqual && !submitting.value
  })

  function setPlayer(position: Position, playerId: number | null) {
    selectedPlayers.value[position] = playerId
  }

  function adjustScore(team: 'orange' | 'blue', delta: number) {
    if (team === 'orange') {
      orangeScore.value = Math.max(0, Math.min(10, orangeScore.value + delta))
    } else {
      blueScore.value = Math.max(0, Math.min(10, blueScore.value + delta))
    }
  }

  const playerCount = computed(() => {
    return Object.values(selectedPlayers.value).filter(id => id !== null).length
  })

  function rotatePlayers() {
    const s = selectedPlayers.value
    if (playerCount.value === 4) {
      // Clockwise: OF→BF→BB→OB→OF
      const temp = s.orange_front
      s.orange_front = s.orange_back
      s.orange_back = s.blue_back
      s.blue_back = s.blue_front
      s.blue_front = temp
    } else if (playerCount.value === 2) {
      // 1v1: swap team AND position (mirrored sides)
      const orangeId = s.orange_front ?? s.orange_back
      const blueId = s.blue_front ?? s.blue_back
      const orangeWasFront = s.orange_front !== null
      const blueWasFront = s.blue_front !== null
      s.orange_front = null
      s.orange_back = null
      s.blue_front = null
      s.blue_back = null
      // Mirror: front→back, back→front on the other team
      if (orangeWasFront) { s.blue_back = orangeId } else { s.blue_front = orangeId }
      if (blueWasFront) { s.orange_back = blueId } else { s.orange_front = blueId }
    }
  }

  function buildPlayers(): MatchPlayerEntry[] {
    const s = selectedPlayers.value
    const is1v1 = playerCount.value === 2
    const players: MatchPlayerEntry[] = []

    if (s.orange_front !== null) {
      players.push({
        player_id: s.orange_front,
        side: 'orange',
        position: is1v1 ? 'solo' : 'voor',
      })
    }
    if (s.orange_back !== null) {
      players.push({
        player_id: s.orange_back,
        side: 'orange',
        position: is1v1 ? 'solo' : 'achter',
      })
    }
    if (s.blue_front !== null) {
      players.push({
        player_id: s.blue_front,
        side: 'blue',
        position: is1v1 ? 'solo' : 'voor',
      })
    }
    if (s.blue_back !== null) {
      players.push({
        player_id: s.blue_back,
        side: 'blue',
        position: is1v1 ? 'solo' : 'achter',
      })
    }

    return players
  }

  async function submitMatch(): Promise<Match> {
    submitting.value = true
    feedback.value = null
    try {
      const payload: MatchCreate = {
        orange_score: orangeScore.value,
        blue_score: blueScore.value,
        players: buildPlayers(),
      }
      const match = await api<Match>('/api/matches', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      feedback.value = 'Match saved!'
      if (sessionStart.value === null) sessionStart.value = Date.now()
      sessionMatches.value.unshift(match)
      resetScores()
      return match
    } catch (e: any) {
      feedback.value = e.message || 'Failed to save match'
      throw e
    } finally {
      submitting.value = false
    }
  }

  async function deleteMatch(id: number) {
    await api('/api/matches/' + id, { method: 'DELETE' })
    sessionMatches.value = sessionMatches.value.filter(m => m.id !== id)
  }

  return {
    orangeScore,
    blueScore,
    selectedPlayers,
    submitting,
    feedback,
    canSubmit,
    setPlayer,
    adjustScore,
    resetScores,
    submitMatch,
    rotatePlayers,
    playerCount,
    sessionMatches,
    sessionExpired,
    deleteMatch,
  }
}
