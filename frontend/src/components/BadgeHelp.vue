<template>
  <div ref="root" class="badge-help" @pointerenter="onEnter" @pointerleave="onLeave" @focusout="onFocusOut">
    <button type="button" class="badge-help-button" :aria-label="`Uitleg over ${label}`"
      :aria-expanded="open" :aria-controls="id" :aria-describedby="open ? id : undefined"
      @click="toggle">i</button>
    <div v-if="open" :id="id" class="badge-help-text" role="note">{{ description }}</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, useId } from 'vue'

defineProps<{ label: string; description: string }>()
const id = useId()
const root = ref<HTMLElement>()
const open = ref(false)
let pinned = false

function close() { open.value = false; pinned = false }
function toggle() { pinned = !pinned; open.value = pinned }
function onEnter(event: PointerEvent) { if (event.pointerType === 'mouse') open.value = true }
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
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onOutside)
  document.removeEventListener('keydown', onKey)
})
</script>

<style scoped>
.badge-help { position: relative; flex: 0 0 auto; margin-left: auto; align-self: flex-start; }
.badge-help:has(.badge-help-text) { z-index: 10; }
.badge-help-button { display: grid; place-items: center; width: 24px; height: 24px; padding: 0; border: 1px solid #596576; border-radius: 50%; background: #253040; color: #d6deea; font: 700 11px/1 Georgia, serif; cursor: pointer; }
.badge-help-button:hover, .badge-help-button[aria-expanded="true"] { border-color: #ffd287; color: #ffd287; }
.badge-help-button:focus-visible { outline: 2px solid #ffd287; outline-offset: 3px; }
.badge-help-text { position: absolute; top: 100%; right: 0; width: min(240px, calc(100vw - 100px)); padding: 12px; border: 1px solid #647086; border-radius: 10px; background: #182231; color: #edf1f7; box-shadow: 0 8px 24px #0008; font: 400 12px/1.6 system-ui, sans-serif; text-transform: none; letter-spacing: normal; white-space: normal; }
</style>
