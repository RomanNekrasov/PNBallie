<template>
  <div
    ref="rootEl"
    class="player-box relative w-[90px] h-[90px] rounded-xl text-white font-semibold text-sm leading-tight flex flex-col items-center justify-center transition-all select-none"
    :class="{ 'ring-2 ring-white/50 scale-105': dragOver, 'opacity-40 scale-95': dragging }"
    :style="[teamStyle, { touchAction: playerName ? 'none' : 'manipulation' }]"
    :draggable="!!playerName"
    @click.stop="handleClick"
    @dragstart="onDragStart"
    @dragend="onDragEnd"
    @dragover.prevent="onDragOver"
    @dragleave="onDragLeave"
    @drop.prevent="onDrop"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerCancel"
    @lostpointercapture="onLostPointerCapture"
    @touchstart.stop
    :data-position="position"
  >
    <span class="player-position-label">{{ label }}</span>
    <div
      v-if="playerName"
      class="player-identity"
      :data-player-id="playerId"
    >
      <CrownIcon v-if="crowned" class="field-crown" />
      <img
        v-if="playerAvatar"
        :src="playerAvatar"
        :alt="`Avatar van ${playerName}`"
        class="player-avatar"
        draggable="false"
      />
      <div v-else class="player-avatar player-avatar-fallback">{{ playerInitials }}</div>
      <span class="player-name" :class="`player-name--${team}`">{{ playerName }}</span>
    </div>
    <span v-else class="player-empty">Kies...</span>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import type { Position } from '../types'
import CrownIcon from './CrownIcon.vue'

const TOUCH_DRAG_THRESHOLD = 8

const props = defineProps<{
  team: 'orange' | 'blue'
  label: string
  playerId: number | null
  playerName: string | null
  playerAvatar: string | null
  crowned: boolean
  position: Position
}>()

const playerInitials = computed(() => {
  if (!props.playerName) return ''
  return props.playerName
    .trim()
    .split(/\s+/)
    .map(part => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
})

const emit = defineEmits<{
  tap: []
  dragstart: [position: Position]
  dragend: []
  dropped: [from: Position, to: Position]
}>()

const rootEl = ref<HTMLElement | null>(null)
const dragOver = ref(false)
const dragging = ref(false)

let activePointerId: number | null = null
let pointerStart = { x: 0, y: 0 }
let pointerPosition = { x: 0, y: 0 }
let ghost: HTMLElement | null = null
let highlightedTarget: HTMLElement | null = null
let animationFrame: number | null = null
let suppressNextClick = false
let clickResetTimer: ReturnType<typeof setTimeout> | null = null

const teamStyle = computed(() => {
  const background = props.team === 'orange' ? '#9f4f1e' : '#244f86'
  const border = props.team === 'orange' ? '#dc7c35' : '#4c82c5'
  return {
    background,
    border: `1px solid ${border}`,
    boxShadow: '0 5px 14px rgba(0, 0, 0, 0.32)',
  }
})

function handleClick() {
  if (suppressNextClick) {
    suppressNextClick = false
    return
  }
  emit('tap')
}

// Native HTML drag remains the desktop interaction.
function onDragStart(e: DragEvent) {
  if (!props.playerName || !e.dataTransfer) return
  dragging.value = true
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', props.position)
  emit('dragstart', props.position)
}

function onDragEnd() {
  dragging.value = false
  dragOver.value = false
  emit('dragend')
}

function onDragOver() {
  dragOver.value = true
}

function onDragLeave() {
  dragOver.value = false
}

function onDrop(e: DragEvent) {
  dragOver.value = false
  const from = e.dataTransfer?.getData('text/plain') as Position | undefined
  if (from && from !== props.position) emit('dropped', from, props.position)
}

function onPointerDown(e: PointerEvent) {
  if (e.pointerType === 'mouse' || !props.playerName || activePointerId !== null) return

  activePointerId = e.pointerId
  pointerStart = { x: e.clientX, y: e.clientY }
  pointerPosition = { ...pointerStart }
  rootEl.value?.setPointerCapture?.(e.pointerId)
}

function onPointerMove(e: PointerEvent) {
  if (e.pointerId !== activePointerId) return
  pointerPosition = { x: e.clientX, y: e.clientY }

  if (!dragging.value) {
    const distance = Math.hypot(
      pointerPosition.x - pointerStart.x,
      pointerPosition.y - pointerStart.y,
    )
    if (distance < TOUCH_DRAG_THRESHOLD) return
    beginPointerDrag()
  }

  e.preventDefault()
  scheduleGhostMove()
  updateHighlightedTarget(e.clientX, e.clientY)
}

function beginPointerDrag() {
  if (!props.playerName) return
  dragging.value = true
  suppressNextClick = true
  emit('dragstart', props.position)

  ghost = document.createElement('div')
  ghost.className = 'touch-drag-ghost'
  ghost.textContent = props.playerName
  document.body.appendChild(ghost)
  scheduleGhostMove()
}

function scheduleGhostMove() {
  if (!ghost || animationFrame !== null) return
  animationFrame = requestAnimationFrame(() => {
    animationFrame = null
    if (!ghost) return
    ghost.style.transform = `translate3d(${pointerPosition.x}px, ${pointerPosition.y}px, 0) translate(-50%, -120%)`
  })
}

function dropTargetAt(x: number, y: number): HTMLElement | null {
  const element = document.elementFromPoint(x, y)
  const target = element?.closest('[data-position]') as HTMLElement | null
  if (!target || target.dataset.position === props.position) return null
  return target
}

function updateHighlightedTarget(x: number, y: number) {
  const target = dropTargetAt(x, y)
  if (target === highlightedTarget) return
  highlightedTarget?.classList.remove('player-drop-target')
  highlightedTarget = target
  highlightedTarget?.classList.add('player-drop-target')
}

function onPointerUp(e: PointerEvent) {
  if (e.pointerId !== activePointerId) return
  const wasDragging = dragging.value
  const target = wasDragging ? dropTargetAt(e.clientX, e.clientY) : null

  cleanupPointer(wasDragging)
  if (target?.dataset.position) {
    emit('dropped', props.position, target.dataset.position as Position)
  }
}

function onPointerCancel(e: PointerEvent) {
  if (e.pointerId === activePointerId) cleanupPointer(dragging.value)
}

function onLostPointerCapture(e: PointerEvent) {
  if (e.pointerId === activePointerId) cleanupPointer(dragging.value)
}

function cleanupPointer(emitDragEnd: boolean) {
  const pointerId = activePointerId
  activePointerId = null

  if (pointerId !== null && rootEl.value?.hasPointerCapture?.(pointerId)) {
    rootEl.value.releasePointerCapture(pointerId)
  }
  if (animationFrame !== null) {
    cancelAnimationFrame(animationFrame)
    animationFrame = null
  }
  ghost?.remove()
  ghost = null
  highlightedTarget?.classList.remove('player-drop-target')
  highlightedTarget = null

  if (emitDragEnd) {
    dragging.value = false
    emit('dragend')
    if (clickResetTimer) clearTimeout(clickResetTimer)
    clickResetTimer = setTimeout(() => { suppressNextClick = false }, 350)
  }
}

onBeforeUnmount(() => cleanupPointer(dragging.value))
</script>

<style scoped>
.player-box {
  overflow: visible;
  -webkit-user-select: none;
  user-select: none;
  -webkit-touch-callout: none;
}

.player-position-label {
  position: absolute;
  bottom: 5px;
  left: 0;
  right: 0;
  text-align: center;
  font-size: 9px;
  line-height: 1;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  opacity: 0.72;
  z-index: 2;
}

.player-identity {
  position: absolute;
  left: 50%;
  top: -37px;
  width: 108px;
  margin-left: -54px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  will-change: transform;
  z-index: 1;
}

.player-avatar {
  position: relative;
  z-index: 1;
  width: 100px;
  height: 100px;
  object-fit: contain;
  object-position: center bottom;
  filter: drop-shadow(0 7px 7px rgba(0, 0, 0, 0.42));
}

.field-crown {
  position: absolute;
  z-index: 4;
  top: -13px;
  left: 50%;
  width: 30px;
  height: auto;
  transform: translateX(-50%) rotate(-7deg);
}

.player-avatar-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.24);
  font-size: 17px;
  font-weight: 800;
}

.player-name {
  --player-accent: #e7b94e;
  position: relative;
  z-index: 2;
  display: block;
  box-sizing: border-box;
  width: 84px;
  margin-top: -20px;
  padding: 1px 8px 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  line-height: 17px;
  font-weight: 900;
  letter-spacing: 0.055em;
  text-align: center;
  text-transform: uppercase;
  color: #fff8dd;
  border: 1px solid rgba(255, 221, 129, 0.9);
  background:
    linear-gradient(110deg, transparent 14%, rgba(255, 255, 255, 0.2) 36%, transparent 58%),
    linear-gradient(180deg, #353b46 0%, #151922 54%, #090b10 100%);
  box-shadow:
    0 3px 7px rgba(0, 0, 0, 0.55),
    inset 0 1px 0 rgba(255, 255, 255, 0.16),
    inset 0 -3px 0 var(--player-accent);
  clip-path: polygon(7px 0, calc(100% - 7px) 0, 100% 50%, calc(100% - 7px) 100%, 7px 100%, 0 50%);
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.9);
}

.player-name--orange {
  --player-accent: #f28a32;
}

.player-name--blue {
  --player-accent: #4387df;
}

.player-empty {
  margin-top: 8px;
  font-size: 13px;
}

.player-box.player-drop-target {
  outline: 2px solid rgba(255, 255, 255, 0.82);
  outline-offset: 3px;
  transform: scale(1.06);
}
</style>
