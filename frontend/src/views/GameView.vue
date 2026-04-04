<template>
  <div class="w-full h-dvh flex items-center justify-center bg-[#1a1510] overflow-hidden">
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
          position="blue_back"
          :player-name="playerName('blue_back')"
          @tap="openModal('blue_back')"
          @dropped="(from, to) => swapPlayers(from, to)"
        />
      </div>

      <!-- Orange Voor / front (top-right) -->
      <div class="absolute top-[18%] right-[4%] z-10">
        <PlayerBox
          team="orange"
          label="Voor"
          position="orange_front"
          :player-name="playerName('orange_front')"
          @tap="openModal('orange_front')"
          @dropped="(from, to) => swapPlayers(from, to)"
        />
      </div>

      <!-- Blue Voor / front (bottom-left) -->
      <div class="absolute bottom-[18%] left-[4%] z-10">
        <PlayerBox
          team="blue"
          label="Voor"
          position="blue_front"
          :player-name="playerName('blue_front')"
          @tap="openModal('blue_front')"
          @dropped="(from, to) => swapPlayers(from, to)"
        />
      </div>

      <!-- Orange Achter / back (bottom-right) -->
      <div class="absolute bottom-[18%] right-[4%] z-10">
        <PlayerBox
          team="orange"
          label="Achter"
          position="orange_back"
          :player-name="playerName('orange_back')"
          @tap="openModal('orange_back')"
          @dropped="(from, to) => swapPlayers(from, to)"
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
import { ref, onMounted, onUnmounted, watch } from 'vue'
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
  rotatePlayers, swapPlayers, playerCount,
  sessionMatches, sessionExpired, deleteMatch,
} = useMatch()

const modalOpen = ref(false)
const modalPosition = ref<Position | null>(null)
const wiggleTeam = ref<'orange' | 'blue' | null>(null)
const historyOpen = ref(false)
const customCursorEl = ref<HTMLElement | null>(null)
const customCursorEnabled = ref(false)
const cursorRotation = ref(0)
const cursorLastPointer = ref<{ x: number; y: number; t: number } | null>(null)
const cursorSuppressedByTouch = ref(false)

function spawnBounce(e: MouseEvent | TouchEvent) {
  if ('touches' in e) {
    suppressCustomCursor()
  }

  const el = document.createElement('div')
  el.className = 'ball-bounce'
  el.textContent = '\u26BD'
  const x = 'touches' in e ? e.touches[0]!.clientX : (e as MouseEvent).clientX
  const y = 'touches' in e ? e.touches[0]!.clientY : (e as MouseEvent).clientY
  el.style.left = `${x}px`
  el.style.top = `${y}px`
  document.body.appendChild(el)
  el.addEventListener('animationend', () => el.remove())
}

function suppressCustomCursor() {
  if (!customCursorEl.value) return
  cursorSuppressedByTouch.value = true
  customCursorEl.value.style.opacity = '0'
}

function revealCustomCursor() {
  if (!customCursorEl.value) return
  cursorSuppressedByTouch.value = false
  customCursorEl.value.style.opacity = '1'
}

function updateCustomCursorPosition(x: number, y: number) {
  if (!customCursorEl.value) return
  customCursorEl.value.style.left = `${x}px`
  customCursorEl.value.style.top = `${y}px`
  customCursorEl.value.style.transform = `translate(-50%, -50%) rotate(${cursorRotation.value}deg)`
}

function onCursorPointerMove(e: PointerEvent) {
  if (!customCursorEnabled.value || !customCursorEl.value) return
  if (e.pointerType === 'touch') {
    suppressCustomCursor()
    return
  }

  if (cursorSuppressedByTouch.value) {
    revealCustomCursor()
  }

  const next = { x: e.clientX, y: e.clientY, t: e.timeStamp }
  const prev = cursorLastPointer.value
  cursorLastPointer.value = next

  if (prev) {
    const dx = next.x - prev.x
    const dy = next.y - prev.y
    const dt = Math.max(1, next.t - prev.t)
    const speed = Math.hypot(dx, dy) / dt
    const influence = 1 + Math.min(2, speed * 5)
    const spinDelta = (dx + dy * 0.55) * 1.25 * influence
    cursorRotation.value = (cursorRotation.value + spinDelta) % 360
  }

  updateCustomCursorPosition(next.x, next.y)
}

function enableCustomCursor() {
  if (!window.matchMedia('(pointer: fine)').matches) return

  const el = document.createElement('div')
  el.className = 'football-cursor-ball'
  el.textContent = '\u26BD'
  el.style.opacity = '0'
  document.body.appendChild(el)

  customCursorEl.value = el
  customCursorEnabled.value = true
  cursorRotation.value = 0
  cursorLastPointer.value = null
  // Start hidden until first real mouse move, then reveal.
  cursorSuppressedByTouch.value = true
  document.body.classList.add('football-cursor')
  document.addEventListener('pointermove', onCursorPointerMove)
}

function disableCustomCursor() {
  document.removeEventListener('pointermove', onCursorPointerMove)
  document.body.classList.remove('football-cursor')
  customCursorEnabled.value = false
  cursorLastPointer.value = null
  if (customCursorEl.value) {
    customCursorEl.value.remove()
    customCursorEl.value = null
  }
}

onMounted(() => {
  fetchPlayers()
  enableCustomCursor()
  document.addEventListener('click', spawnBounce)
  document.addEventListener('touchstart', spawnBounce, { passive: true })
})

onUnmounted(() => {
  disableCustomCursor()
  document.removeEventListener('click', spawnBounce)
  document.removeEventListener('touchstart', spawnBounce)
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
body.football-cursor,
body.football-cursor * {
  cursor: none !important;
}

.football-cursor-ball {
  position: fixed;
  left: 0;
  top: 0;
  width: 28px;
  height: 28px;
  pointer-events: none;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  line-height: 1;
  transform: translate(-50%, -50%) rotate(0deg);
  will-change: transform, left, top;
  filter: drop-shadow(0 1px 1px rgba(0, 0, 0, 0.55));
  transition: opacity 0.12s ease;
}

@keyframes ball-bounce {
  0%   { transform: translate(-50%, -50%) scale(1); opacity: 1; }
  30%  { transform: translate(-50%, -80%) scale(1.2); opacity: 1; }
  50%  { transform: translate(-50%, -50%) scale(0.9); opacity: 0.9; }
  70%  { transform: translate(-50%, -65%) scale(1.05); opacity: 0.7; }
  100% { transform: translate(-50%, -50%) scale(0); opacity: 0; }
}

.ball-bounce {
  position: fixed;
  pointer-events: none;
  font-size: 28px;
  z-index: 9999;
  animation: ball-bounce 0.5s ease-out forwards;
}

.touch-drag-ghost {
  position: fixed;
  pointer-events: none;
  z-index: 9999;
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 10px;
  padding: 8px 16px;
  color: white;
  font-size: 14px;
  font-weight: 600;
  transform: translate(-50%, -120%);
  white-space: nowrap;
}

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
