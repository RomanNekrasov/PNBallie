<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 bg-black/70 flex flex-col"
      @click.self="$emit('close')"
    >
      <div class="flex-1 flex flex-col items-center justify-center p-6 overflow-y-auto">
        <h2 class="text-white text-xl font-bold mb-2 text-center">Kies speler</h2>
        <p class="text-white/55 text-sm mb-6 text-center">{{ positionLabel }}</p>

        <div class="grid grid-cols-2 gap-3 max-w-[340px] w-full">
          <button
            v-for="player in players"
            :key="player.id"
            @click="select(player.id)"
            :disabled="disabledIds.has(player.id)"
            class="player-choice aspect-square rounded-2xl text-white font-semibold text-base flex flex-col items-center justify-center text-center p-2 transition-all leading-tight relative overflow-hidden"
            :class="[
              disabledIds.has(player.id)
                ? 'player-choice-disabled opacity-30 cursor-not-allowed'
                : currentPlayerId === player.id
                  ? 'player-choice-selected ring-2 ring-white active:scale-95'
                  : 'player-choice-default active:scale-95'
            ]"
          >
            <span v-if="currentPlayerId === player.id" class="selected-check" aria-label="Huidige selectie">✓</span>
            <span class="choice-avatar-wrap">
              <CrownIcon v-if="leaderIds.has(player.id)" class="choice-crown" />
              <img
                v-if="playerAvatar(player.name, player.avatar_url)"
                :src="playerAvatar(player.name, player.avatar_url)!"
                :alt="`Avatar van ${player.name}`"
                class="choice-avatar"
                draggable="false"
              />
              <span v-else class="choice-avatar choice-avatar-fallback">{{ playerInitials(player.name) }}</span>
            </span>
            <span class="choice-name">{{ player.name }}</span>
            <span v-if="selectedPosition(player.id)" class="choice-status">{{ selectedPosition(player.id) }}</span>
          </button>
        </div>

        <button
          v-if="currentPlayerId !== null"
          @click="select(null)"
          class="remove-choice mt-4 py-3 px-6 rounded-xl text-center text-red-300 font-medium"
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
import { playerAvatar, playerInitials } from '../playerAvatar'
import CrownIcon from './CrownIcon.vue'

const props = defineProps<{
  open: boolean
  players: Player[]
  currentPlayerId: number | null
  selectedPlayers: Record<Position, number | null>
  leaderPlayerIds: number[]
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

const leaderIds = computed(() => new Set(props.leaderPlayerIds))

const POSITION_LABELS: Record<Position, string> = {
  orange_front: 'Oranje · voor',
  orange_back: 'Oranje · achter',
  blue_front: 'Blauw · voor',
  blue_back: 'Blauw · achter',
}

const positionLabel = computed(() => POSITION_LABELS[props.position])

function selectedPosition(playerId: number): string | null {
  const entry = Object.entries(props.selectedPlayers).find(([, id]) => id === playerId)
  if (!entry) return null
  return entry[0] === props.position ? 'Geselecteerd' : POSITION_LABELS[entry[0] as Position]
}

function select(playerId: number | null) {
  emit('select', playerId)
  emit('close')
}
</script>

<style scoped>
.player-choice {
  min-height: 146px;
  border: 1px solid #46515f;
}

.player-choice-default {
  background: #252d37;
}

.player-choice-default:active {
  background: #313b47;
}

.player-choice-selected {
  background: #3c4b5e;
}

.player-choice-disabled {
  background: #161b21;
}

.remove-choice {
  background: #282126;
}

.remove-choice:active {
  background: #3a282f;
}

.choice-avatar {
  width: 86px;
  height: 86px;
  object-fit: contain;
  object-position: center bottom;
  filter: drop-shadow(0 7px 8px rgba(0, 0, 0, 0.38));
  pointer-events: none;
}

.choice-avatar-wrap {
  position: relative;
  display: grid;
  place-items: center;
}

.choice-crown {
  position: absolute;
  z-index: 2;
  top: -11px;
  left: 50%;
  width: 28px;
  height: auto;
  transform: translateX(-50%) rotate(-7deg);
}

.choice-avatar-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.2);
  font-size: 26px;
  font-weight: 800;
}

.choice-name {
  max-width: 125px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 16px;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.8);
}

.choice-status {
  margin-top: 3px;
  color: rgba(255, 255, 255, 0.58);
  font-size: 10px;
  font-weight: 500;
}

.selected-check {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border-radius: 9999px;
  color: #132218;
  background: #7cf2a9;
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.28);
}
</style>
