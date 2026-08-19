<template>
  <div
    ref="rootEl"
    class="player-box w-[90px] h-[90px] rounded-xl text-white font-semibold text-sm leading-tight flex flex-col items-center justify-center transition-all select-none"
    :class="{ 'ring-2 ring-white/50 scale-105': dragOver, 'opacity-40 scale-95': dragging }"
    :style="[glassStyle, { touchAction: playerName ? 'none' : 'manipulation' }]"
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
    <span class="text-[10px] uppercase tracking-wider opacity-75">{{ label }}</span>
    <span class="truncate max-w-[90px]">{{ playerName || 'Kies...' }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import type { Position } from '../types'

const TOUCH_DRAG_THRESHOLD = 8

const props = defineProps<{
  team: 'orange' | 'blue'
  label: string
  playerName: string | null
  position: Position
}>()

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

const glassStyle = computed(() => {
  const color = props.team === 'orange' ? '217, 124, 46' : '45, 95, 161'
  return {
    background: `rgba(${color}, 0.45)`,
    backdropFilter: 'blur(16px) saturate(180%)',
    WebkitBackdropFilter: 'blur(16px) saturate(180%)',
    border: `1px solid rgba(${color}, 0.65)`,
    boxShadow: `0 4px 24px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.2)`,
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
  -webkit-user-select: none;
  user-select: none;
  -webkit-touch-callout: none;
}

.player-box.player-drop-target {
  outline: 2px solid rgba(255, 255, 255, 0.82);
  outline-offset: 3px;
  transform: scale(1.06);
}
</style>
