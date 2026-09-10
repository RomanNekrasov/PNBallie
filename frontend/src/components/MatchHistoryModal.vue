<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 bg-black/70 flex flex-col"
      @click.self="$emit('close')"
    >
      <div class="flex-1 flex flex-col items-center justify-center p-6 overflow-y-auto">
        <h2 class="text-white text-xl font-bold mb-6 text-center">Gespeelde wedstrijden</h2>

        <div v-if="matches.length === 0" class="text-white/50 text-center">
          Nog geen wedstrijden deze sessie
        </div>

        <div class="w-full max-w-[340px] space-y-3">
          <div
            v-for="match in matches"
            :key="match.id"
            class="history-card rounded-2xl p-4 flex items-center justify-between"
          >
            <div class="flex-1 min-w-0">
              <time class="history-time" :datetime="match.played_at">{{ formatLocalDateTime(match.played_at) }}</time>
              <div class="history-result">
                <span class="history-team text-[#e87d2f]">{{ orangeNames(match) }}</span>
                <div class="history-score text-lg font-bold" :aria-label="`Oranje ${match.orange_score}, Blauw ${match.blue_score}`">
                  <span class="text-[#e87d2f]">{{ match.orange_score }}</span>
                  <span class="text-white/40">–</span>
                  <span class="text-[#4a90d9]">{{ match.blue_score }}</span>
                </div>
                <span class="history-team history-team-blue text-[#4a90d9]">{{ blueNames(match) }}</span>
              </div>
            </div>
            <button
              v-if="canDelete"
              @click="$emit('delete', match.id)"
              :aria-label="`Wedstrijd ${orangeNames(match)} tegen ${blueNames(match)} verwijderen`"
              class="ml-3 w-9 h-9 rounded-full flex items-center justify-center text-red-400/60 active:text-red-400 active:scale-90 transition-all shrink-0"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <div class="p-4 flex justify-center pb-[env(safe-area-inset-bottom)]">
        <button
          @click="$emit('close')"
          class="close-button px-6 py-3 rounded-xl text-white font-semibold"
        >
          Sluiten
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import type { Match } from '../types'
import type { Player } from '../types'
import { formatLocalDateTime } from '../dateTime'

const props = defineProps<{
  open: boolean
  matches: Match[]
  players: Player[]
  canDelete: boolean
}>()

defineEmits<{
  close: []
  delete: [id: number]
}>()

function getPlayerName(id: number): string {
  return props.players.find(p => p.id === id)?.name ?? '?'
}

function orangeNames(match: Match): string {
  return match.players
    .filter(mp => mp.side === 'orange')
    .map(mp => getPlayerName(mp.player_id))
    .join(' & ')
}

function blueNames(match: Match): string {
  return match.players
    .filter(mp => mp.side === 'blue')
    .map(mp => getPlayerName(mp.player_id))
    .join(' & ')
}
</script>

<style scoped>
.history-card {
  border: 1px solid #46515f;
  background: #252d37;
}
.history-time { display: block; margin-bottom: 9px; color: #b2bcc9; font-size: 10px; }
.history-result { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: center; gap: 8px; }
.history-team { overflow-wrap: anywhere; font-size: 12px; line-height: 1.4; }
.history-team-blue { text-align: right; }
.history-score { display: flex; align-items: center; gap: 5px; }

.close-button {
  border: 1px solid #46515f;
  background: #252d37;
}

.close-button:active {
  background: #313b47;
}
</style>
