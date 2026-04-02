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
            class="rounded-2xl p-4 flex items-center justify-between"
            style="
              background: rgba(255,255,255,0.08);
              backdrop-filter: blur(16px) saturate(180%);
              -webkit-backdrop-filter: blur(16px) saturate(180%);
              border: 1px solid rgba(255,255,255,0.15);
            "
          >
            <div class="flex-1 min-w-0">
              <!-- Score line -->
              <div class="flex items-center gap-2 text-lg font-bold">
                <span class="text-[#e87d2f]">{{ match.orange_score }}</span>
                <span class="text-white/40">-</span>
                <span class="text-[#4a90d9]">{{ match.blue_score }}</span>
              </div>
              <!-- Players -->
              <div class="text-xs text-white/50 mt-1 leading-relaxed">
                <span class="text-[#e87d2f]/70">{{ orangeNames(match) }}</span>
                <span class="text-white/30"> vs </span>
                <span class="text-[#4a90d9]/70">{{ blueNames(match) }}</span>
              </div>
            </div>
            <button
              v-if="canDelete"
              @click="$emit('delete', match.id)"
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
          class="px-6 py-3 rounded-xl text-white font-semibold bg-white/10 active:bg-white/20"
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
