<template>
  <div class="w-full h-dvh flex items-center justify-center bg-[#1a1a2e] overflow-hidden">
    <div class="relative w-full max-w-[420px] h-full max-h-[800px]">
      <!-- SVG Table Background -->
      <FoosballTable class="absolute inset-0 w-full h-full" :wiggle="wiggleTeam" />

      <!-- Orange Score (top center) -->
      <div class="absolute top-[2%] left-1/2 -translate-x-1/2 z-10">
        <ScoreBox
          :score="orangeScore"
          team="orange"
          @adjust="(d) => adjustScore('orange', d)"
          @update:score="(v) => orangeScore = v"
        />
      </div>

      <!-- Blue Achter / back (top-left) -->
      <div class="absolute top-[18%] left-[4%] z-10">
        <PlayerBox
          team="blue"
          label="Achter"
          :player-name="playerName('blue_back')"
          @tap="openModal('blue_back')"
        />
      </div>

      <!-- Orange Voor / front (top-right) -->
      <div class="absolute top-[18%] right-[4%] z-10">
        <PlayerBox
          team="orange"
          label="Voor"
          :player-name="playerName('orange_front')"
          @tap="openModal('orange_front')"
        />
      </div>

      <!-- Blue Voor / front (bottom-left) -->
      <div class="absolute bottom-[18%] left-[4%] z-10">
        <PlayerBox
          team="blue"
          label="Voor"
          :player-name="playerName('blue_front')"
          @tap="openModal('blue_front')"
        />
      </div>

      <!-- Orange Achter / back (bottom-right) -->
      <div class="absolute bottom-[18%] right-[4%] z-10">
        <PlayerBox
          team="orange"
          label="Achter"
          :player-name="playerName('orange_back')"
          @tap="openModal('orange_back')"
        />
      </div>

      <!-- Center buttons -->
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 flex flex-col items-center gap-3">
        <SubmitButton
          :disabled="!canSubmit"
          :submitting="submitting"
          @submit="handleSubmit"
        />
        <div class="flex items-center gap-3">
          <button
            v-if="playerCount >= 2"
            @click="rotatePlayers"
            class="glass-btn"
            :title="playerCount === 2 ? 'Wissel zijdes' : 'Roteer spelers'"
          >
            <svg v-if="playerCount >= 4" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12a9 9 0 1 1-6.22-8.56" />
              <polyline points="21 3 21 9 15 9" />
            </svg>
            <svg v-else xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="17 1 21 5 17 9" />
              <path d="M3 11V9a4 4 0 0 1 4-4h14" />
              <polyline points="7 23 3 19 7 15" />
              <path d="M21 13v2a4 4 0 0 1-4 4H3" />
            </svg>
          </button>
          <button
            v-if="sessionMatches.length > 0"
            @click="historyOpen = true"
            class="glass-btn relative"
            title="Wedstrijden"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" />
              <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
              <path d="M4 22h16" />
              <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20 7 22" />
              <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20 17 22" />
              <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" />
            </svg>
            <span class="absolute -top-1 -right-1 bg-white/30 text-white text-[10px] font-bold w-5 h-5 rounded-full flex items-center justify-center">
              {{ sessionMatches.length }}
            </span>
          </button>
        </div>
      </div>

      <!-- Blue Score (bottom center) -->
      <div class="absolute bottom-[2%] left-1/2 -translate-x-1/2 z-10 pb-[env(safe-area-inset-bottom)]">
        <ScoreBox
          :score="blueScore"
          team="blue"
          @adjust="(d) => adjustScore('blue', d)"
          @update:score="(v) => blueScore = v"
        />
      </div>

      <!-- Feedback toast -->
      <Transition name="fade">
        <div
          v-if="feedback"
          class="absolute top-[8%] left-1/2 -translate-x-1/2 z-20 bg-black/80 text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          {{ feedback }}
        </div>
      </Transition>
    </div>

    <!-- Match History Modal -->
    <MatchHistoryModal
      :open="historyOpen"
      :matches="sessionMatches"
      :players="players"
      :can-delete="!sessionExpired"
      @close="historyOpen = false"
      @delete="handleDeleteMatch"
    />

    <!-- Player Select Modal -->
    <PlayerSelectModal
      :open="modalOpen"
      :players="players"
      :current-player-id="modalPosition ? selectedPlayers[modalPosition] : null"
      :selected-players="selectedPlayers"
      :position="modalPosition!"
      @close="modalOpen = false"
      @select="handlePlayerSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import type { Position } from '../types'
import { usePlayers } from '../composables/usePlayers'
import { useMatch } from '../composables/useMatch'
import FoosballTable from '../components/FoosballTable.vue'
import ScoreBox from '../components/ScoreBox.vue'
import PlayerBox from '../components/PlayerBox.vue'
import PlayerSelectModal from '../components/PlayerSelectModal.vue'
import SubmitButton from '../components/SubmitButton.vue'
import MatchHistoryModal from '../components/MatchHistoryModal.vue'

const { players, fetchPlayers } = usePlayers()
const {
  orangeScore, blueScore, selectedPlayers,
  submitting, feedback, canSubmit,
  setPlayer, adjustScore, submitMatch,
  rotatePlayers, playerCount,
  sessionMatches, sessionExpired, deleteMatch,
} = useMatch()

const modalOpen = ref(false)
const modalPosition = ref<Position | null>(null)
const wiggleTeam = ref<'orange' | 'blue' | null>(null)
const historyOpen = ref(false)

onMounted(() => {
  fetchPlayers()
})

// Auto-dismiss feedback
watch(feedback, (val) => {
  if (val) {
    setTimeout(() => { feedback.value = null }, 2500)
  }
})

function playerName(position: Position): string | null {
  const id = selectedPlayers.value[position]
  if (id === null) return null
  return players.value.find(p => p.id === id)?.name ?? null
}

function openModal(position: Position) {
  modalPosition.value = position
  modalOpen.value = true
}

function handlePlayerSelect(playerId: number | null) {
  if (modalPosition.value) {
    setPlayer(modalPosition.value, playerId)
  }
}

async function handleDeleteMatch(id: number) {
  await deleteMatch(id)
}

async function handleSubmit() {
  const os = orangeScore.value
  const bs = blueScore.value
  try {
    await submitMatch()
    wiggleTeam.value = os > bs ? 'orange' : 'blue'
    setTimeout(() => { wiggleTeam.value = null }, 1500)
  } catch {
    // feedback is already set by useMatch
  }
}
</script>

<style>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
.glass-btn {
  width: 44px;
  height: 44px;
  border-radius: 9999px;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.15s;
  background: rgba(255,255,255,0.12);
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  border: 1px solid rgba(255,255,255,0.2);
  box-shadow: 0 4px 24px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
}
.glass-btn:active {
  transform: scale(0.9);
}
</style>
