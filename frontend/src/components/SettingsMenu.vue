<template>
  <div ref="container" class="settings-menu" @keydown.esc.stop.prevent="close(true)" @focusout="onFocusOut">
    <button
      ref="trigger"
      class="settings-toggle"
      type="button"
      aria-label="Instellingen en account"
      title="Instellingen en account"
      :aria-expanded="open"
      :aria-controls="panelId"
      @click="toggle"
      @keydown.down.prevent="openAndFocus"
    >
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="m9.4 3-.6 2.3-1.6.9L5 5.6 2.4 10l1.7 1.7v1.8L2.4 15 5 19.4l2.2-.6 1.6.9.6 2.3h5.2l.6-2.3 1.6-.9 2.2.6 2.6-4.4-1.7-1.5v-1.8l1.7-1.7L19 5.6l-2.2.6-1.6-.9L14.6 3Z" />
        <circle cx="12" cy="12.5" r="3.2" />
      </svg>
    </button>
    <div v-if="open" :id="panelId" class="settings-panel">
      <p class="settings-group"><span>{{ currentGroup ? 'Huidige groep' : 'PNBallie' }}</span><strong>{{ currentGroup?.name ?? authUser?.display_name }}</strong></p>
      <nav aria-label="Instellingen en account">
        <RouterLink v-if="currentGroup" to="/profile" class="settings-link" @click="close()">Mijn profiel</RouterLink>
        <RouterLink to="/groups" class="settings-link" @click="close()">Groepen</RouterLink>
        <RouterLink v-if="isGroupAdmin" to="/admin" class="settings-link" @click="close()">Groepsbeheer</RouterLink>
      </nav>
      <button class="settings-link settings-logout" type="button" :disabled="busy" @click="signOut">{{ busy ? 'Uitloggen…' : 'Uitloggen' }}</button>
      <p v-if="error" class="settings-error" role="alert">{{ error }}</p>
      <AnalyticsNotice />
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authUser, currentGroup, isGroupAdmin, logout } from '../auth'
import AnalyticsNotice from './AnalyticsNotice.vue'

const router = useRouter()
const route = useRoute()
const container = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const panelId = `settings-${useId()}`
const open = ref(false)
const busy = ref(false)
const error = ref('')

function close(restoreFocus = false) {
  open.value = false
  if (restoreFocus) trigger.value?.focus()
}
function toggle() {
  open.value = !open.value
  error.value = ''
}
async function openAndFocus() {
  open.value = true
  await nextTick()
  container.value?.querySelector<HTMLAnchorElement>('.settings-link')?.focus()
}
function onPointerDown(event: PointerEvent) {
  if (event.target instanceof Node && !container.value?.contains(event.target)) close()
}
function onFocusOut(event: FocusEvent) {
  if (event.relatedTarget instanceof Node && !container.value?.contains(event.relatedTarget)) close()
}
async function signOut() {
  busy.value = true
  error.value = ''
  try {
    await logout()
    close()
    await router.replace('/login')
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Uitloggen is niet gelukt. Probeer het opnieuw.'
  } finally {
    busy.value = false
  }
}
watch(() => route.fullPath, () => close())
onMounted(() => document.addEventListener('pointerdown', onPointerDown))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onPointerDown))
</script>

<style scoped>
.settings-menu { position: relative; flex: 0 0 auto; z-index: 40; }
.settings-toggle { display: grid; place-items: center; width: 44px; height: 44px; padding: 0; border: 1px solid #435069; border-radius: 12px; color: #becce0; background: #1c2736; transition: background .15s, border-color .15s, color .15s; }
.settings-toggle[aria-expanded=true] { border-color: #d99962; color: #ffd0a0; background: #3b2e26; }
.settings-panel { position: absolute; top: calc(100% + 9px); right: 0; width: min(240px, calc(100vw - 28px)); padding: 8px; border: 1px solid #47556a; border-radius: 14px; background: #182231; box-shadow: 0 15px 40px #0007; color: #e5edf8; }
.settings-group { display: grid; gap: 5px; padding: 9px 10px 12px; margin: 0 0 5px; border-bottom: 1px solid #394456; }
.settings-group span { font-size: 10px; font-weight: 500; color: #a7b7cb; }
.settings-group strong { font-size: 12px; line-height: 1.4; font-weight: 600; overflow-wrap: anywhere; }
.settings-panel nav { display: grid; gap: 2px; }
.settings-link { display: flex; width: 100%; align-items: center; min-height: 42px; padding: 10px; border: 1px solid transparent; border-radius: 8px; text-decoration: none; text-align: left; color: #e0e9f7; background: transparent; font: 600 12px/1.4 system-ui, sans-serif; transition: background .15s, color .15s, border-color .15s; }
.settings-link.router-link-active { color: #ffd0a0; background: #3a2b21; }
.settings-logout { margin-top: 6px; color: #b5c5db; }
.settings-error { margin: 6px 4px 4px; padding: 9px; border-radius: 7px; background: #3c2530; color: #ffc1ca; font-size: 11px; line-height: 1.5; overflow-wrap: anywhere; }
@media (hover: hover) {
  .settings-toggle:hover { background: #33455d; border-color: #91a6c4; color: #fff; }
  .settings-link:hover:not(:disabled) { background: #32465f; border-color: #596f8d; color: #fff; }
}
</style>
