<template>
  <div ref="root" class="badge-help" :class="{ 'badge-help--card': card }" @pointerenter="onEnter" @pointerleave="onLeave" @focusout="onFocusOut">
    <button type="button" class="badge-help-button" :aria-label="card ? undefined : `Uitleg over ${label}`"
      :aria-expanded="open" :aria-controls="id" :aria-describedby="open ? id : undefined"
      @pointerdown="onPointerDown" @touchstart.passive="onTouchStart" @click="toggle"><slot>i</slot></button>
    <div v-if="open" :id="id" class="badge-help-text" role="note">{{ description }}</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, useId } from 'vue'

defineProps<{ label: string; description: string; card?: boolean }>()
const id = useId()
const root = ref<HTMLElement>()
const open = ref(false)
let pinned = false
let pointerType = 'mouse'

function close() { open.value = false; pinned = false }
function onPointerDown(event: PointerEvent) { pointerType = event.pointerType }
function onTouchStart() { pointerType = 'touch' }
function toggle(event: MouseEvent) {
  // Touch browsers may emit a mouse-compatible click. Keep the original input
  // type; real mouse clicks never pin, while keyboard activation has detail 0.
  if (event.detail > 0 && pointerType === 'mouse') return
  pinned = !pinned
  open.value = pinned
}
function onEnter(event: PointerEvent) {
  if (event.pointerType === 'mouse') { pinned = false; open.value = true }
}
function onLeave() { if (!pinned) open.value = false }
function onFocusOut(event: FocusEvent) {
  if (!root.value?.contains(event.relatedTarget as Node | null)) close()
}
function onOutside(event: PointerEvent) {
  if (!root.value?.contains(event.target as Node)) close()
}
function onKey(event: KeyboardEvent) { if (event.key === 'Escape') close() }
onMounted(() => {
  document.addEventListener('pointerdown', onOutside)
  document.addEventListener('keydown', onKey)
  window.addEventListener('scroll', close, { capture: true, passive: true })
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onOutside)
  document.removeEventListener('keydown', onKey)
  window.removeEventListener('scroll', close, true)
})
</script>

<style scoped>
.badge-help { position: relative; flex: 0 0 auto; margin-left: auto; align-self: flex-start; }
.badge-help:has(.badge-help-text) { z-index: 10; }
.badge-help-button { display: grid; place-items: center; width: 24px; height: 24px; padding: 0; border: 1px solid #596576; border-radius: 50%; background: #253040; color: #d6deea; font: 700 11px/1 Georgia, serif; cursor: pointer; }
.badge-help-button:hover, .badge-help-button[aria-expanded="true"] { border-color: #ffd287; color: #ffd287; }
.badge-help-button:focus-visible { outline: 2px solid #ffd287; outline-offset: 3px; }
.badge-help--card { min-width: 0; margin-left: 0; align-self: stretch; }
.badge-help--card .badge-help-button { display: flex; align-items: center; gap: 12px; width: 100%; height: 100%; min-width: 0; padding: 11px; border: 1px solid var(--line, #596576); border-radius: 13px; background: var(--panel-soft, #253040); color: inherit; font: inherit; text-align: left; }
.badge-help--card .badge-help-button:hover, .badge-help--card .badge-help-button[aria-expanded="true"] { border-color: #ffd287; }
.badge-help-text { position: absolute; top: 100%; right: 0; width: min(240px, calc(100vw - 100px)); padding: 12px; border: 1px solid #647086; border-radius: 10px; background: #182231; color: #edf1f7; box-shadow: 0 8px 24px #0008; font: 400 12px/1.6 system-ui, sans-serif; text-transform: none; letter-spacing: normal; white-space: normal; }
</style>
