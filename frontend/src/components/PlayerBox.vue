<template>
  <div
    class="w-[90px] h-[90px] rounded-xl text-white font-semibold text-sm leading-tight flex flex-col items-center justify-center transition-all select-none"
    :class="{ 'ring-2 ring-white/50 scale-105': dragOver, 'opacity-40 scale-95': dragging }"
    :style="glassStyle"
    :draggable="!!playerName"
    @click="handleClick"
    @dragstart="onDragStart"
    @dragend="onDragEnd"
    @dragover.prevent="onDragOver"
    @dragleave="onDragLeave"
    @drop.prevent="onDrop"
    @touchstart="onTouchStart"
    @touchmove.prevent="onTouchMove"
    @touchend="onTouchEnd"
    :data-position="position"
  >
    <span class="text-[10px] uppercase tracking-wider opacity-75">{{ label }}</span>
    <span class="truncate max-w-[90px]">{{ playerName || 'Kies...' }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Position } from '../types'

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

const dragOver = ref(false)
const dragging = ref(false)
let touchTimeout: ReturnType<typeof setTimeout> | null = null
let isDraggingTouch = false
let ghost: HTMLElement | null = null

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
  if (!isDraggingTouch) {
    emit('tap')
  }
}

// HTML5 drag (desktop)
function onDragStart(e: DragEvent) {
  dragging.value = true
  e.dataTransfer!.effectAllowed = 'move'
  e.dataTransfer!.setData('text/plain', props.position)
  emit('dragstart', props.position)
}

function onDragEnd() {
  dragging.value = false
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
  const from = e.dataTransfer!.getData('text/plain') as Position
  if (from && from !== props.position) {
    emit('dropped', from, props.position)
  }
}

// Touch drag (mobile)
function onTouchStart(e: TouchEvent) {
  isDraggingTouch = false
  touchTimeout = setTimeout(() => {
    if (!props.playerName) return
    isDraggingTouch = true
    dragging.value = true
    emit('dragstart', props.position)

    // Create floating ghost
    const touch = e.touches[0]!
    ghost = document.createElement('div')
    ghost.textContent = props.playerName
    ghost.className = 'touch-drag-ghost'
    ghost.style.left = `${touch.clientX}px`
    ghost.style.top = `${touch.clientY}px`
    document.body.appendChild(ghost)

    // Haptic feedback if available
    if (navigator.vibrate) navigator.vibrate(30)
  }, 300)
}

function onTouchMove(e: TouchEvent) {
  if (!isDraggingTouch) {
    if (touchTimeout) { clearTimeout(touchTimeout); touchTimeout = null }
    return
  }
  const touch = e.touches[0]!
  if (ghost) {
    ghost.style.left = `${touch.clientX}px`
    ghost.style.top = `${touch.clientY}px`
  }

  // Highlight drop target
  const el = document.elementFromPoint(touch.clientX, touch.clientY)
  const target = el?.closest('[data-position]') as HTMLElement | null
  document.querySelectorAll('[data-position]').forEach(n => n.classList.remove('ring-2', 'ring-white/50', 'scale-105'))
  if (target && target.dataset.position !== props.position) {
    target.classList.add('ring-2', 'ring-white/50', 'scale-105')
  }
}

function onTouchEnd(e: TouchEvent) {
  if (touchTimeout) { clearTimeout(touchTimeout); touchTimeout = null }
  if (ghost) { ghost.remove(); ghost = null }

  if (!isDraggingTouch) return
  dragging.value = false

  const touch = e.changedTouches[0]!
  const el = document.elementFromPoint(touch.clientX, touch.clientY)
  const target = el?.closest('[data-position]') as HTMLElement | null
  document.querySelectorAll('[data-position]').forEach(n => n.classList.remove('ring-2', 'ring-white/50', 'scale-105'))

  if (target && target.dataset.position && target.dataset.position !== props.position) {
    emit('dropped', props.position, target.dataset.position as Position)
  }

  emit('dragend')
  // Prevent the click that follows touchend
  setTimeout(() => { isDraggingTouch = false }, 100)
}
</script>
