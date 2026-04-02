<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 bg-black/70 flex flex-col"
      @click.self="$emit('close')"
    >
      <div class="flex-1 flex flex-col items-center justify-center p-6 overflow-y-auto">
        <h2 class="text-white text-xl font-bold mb-6 text-center">Kies speler</h2>

        <div class="grid grid-cols-2 gap-3 max-w-[280px] w-full">
          <button
            v-for="player in players"
            :key="player.id"
            @click="select(player.id)"
            :disabled="disabledIds.has(player.id)"
            class="aspect-square rounded-2xl text-white font-semibold text-base flex items-center justify-center text-center p-2 transition-all leading-tight"
            :class="[
              disabledIds.has(player.id)
                ? 'bg-white/5 opacity-30 cursor-not-allowed'
                : currentPlayerId === player.id
                  ? 'bg-white/30 ring-2 ring-white active:scale-95'
                  : 'bg-white/12 active:scale-95 active:bg-white/20'
            ]"
          >
            <span class="truncate">{{ player.name }}</span>
          </button>
        </div>

        <button
          v-if="currentPlayerId !== null"
          @click="select(null)"
          class="mt-4 py-3 px-6 rounded-xl text-center text-red-300 bg-white/5 active:bg-white/10 font-medium"
        >
          Verwijder selectie
        </button>
      </div>

    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Player, Position } from '../types'

const props = defineProps<{
  open: boolean
  players: Player[]
  currentPlayerId: number | null
  selectedPlayers: Record<Position, number | null>
  position: Position
}>()

const emit = defineEmits<{
  close: []
  select: [playerId: number | null]
}>()

const disabledIds = computed(() => {
  const ids = new Set<number>()
  for (const [pos, id] of Object.entries(props.selectedPlayers)) {
    if (id !== null && pos !== props.position) {
      ids.add(id)
    }
  }
  return ids
})

function select(playerId: number | null) {
  emit('select', playerId)
  emit('close')
}
</script>
