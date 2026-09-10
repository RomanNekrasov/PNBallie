<template>
  <main class="account-page">
    <header class="account-heading">
      <div><p class="account-kicker">WELKOM, {{ authUser?.display_name }}</p><h1 class="account-title">Jouw groepen</h1><p class="account-muted">Elke groep heeft zijn eigen competitie.</p></div>
      <div class="account-heading-actions"><RouterLink v-if="currentGroup" to="/stats" class="account-back-link" aria-label="Terug naar clubstatistieken" title="Terug naar clubstatistieken"><span aria-hidden="true">←</span></RouterLink><SettingsMenu /></div>
    </header>
    <p v-if="error" class="account-error" role="alert">{{ error }}</p>
    <section v-if="groups.length" class="group-grid" aria-label="Je competities">
      <button v-for="group in groups" :key="group.id" class="group-card" :class="{ selected: group.id === currentGroup?.id }" @click="openGroup(group.id)">
        <span class="group-emblem" aria-hidden="true">⚽</span>
        <strong>{{ group.name }}</strong><small>{{ group.role === 'admin' ? 'Beheerder' : 'Speler' }}</small>
        <span class="group-open">Open competitie <span aria-hidden="true">→</span></span>
      </button>
    </section>
    <p v-else class="account-notice">Je bent nog geen lid van een groep. Gebruik een uitnodigingscode of start je eigen competitie.</p>
    <div class="account-columns">
      <section class="account-panel">
        <p class="account-kicker">SPEEL MEE</p><h2>Sluit je aan</h2>
        <p class="account-muted">Vul de code of uitnodigingslink van je beheerder in.</p>
        <form class="account-form" @submit.prevent="joinGroup">
          <label>Uitnodiging<input v-model="invite" autocomplete="off" required maxlength="512" spellcheck="false" placeholder="Code of link" /></label>
          <button class="primary-button" type="submit" :disabled="busy">{{ busy ? 'Even geduld…' : 'Lid worden' }}</button>
        </form>
      </section>
      <section class="account-panel">
        <p class="account-kicker">BEGIN JE EIGEN POOL</p><h2>Nieuwe groep</h2>
        <p class="account-muted">Jij wordt beheerder en kunt daarna spelers uitnodigen.</p>
        <form class="account-form" @submit.prevent="createGroup">
          <label>Groepsnaam<input v-model="name" required maxlength="80" placeholder="Bijvoorbeeld: De kantinetoppers" /></label>
          <button class="secondary-button" type="submit" :disabled="busy">Groep maken</button>
        </form>
      </section>
    </div>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authUser, currentGroup, groups, refreshGroups, selectGroup, type Group } from '../auth'
import { api } from '../composables/useApi'
import SettingsMenu from '../components/SettingsMenu.vue'
import { trackEvent } from '../analytics'

const router = useRouter()
const route = useRoute()
const invite = ref(typeof route.params.code === 'string' ? route.params.code : '')
const name = ref('')
const busy = ref(false)
const error = ref('')

async function openGroup(id: number) {
  selectGroup(id)
  await router.push('/')
}
async function saveGroup(path: string, payload: object) {
  error.value = ''
  busy.value = true
  try {
    const group = await api<Group>(path, { method: 'POST', body: JSON.stringify(payload) })
    trackEvent(path === '/api/groups/join' ? 'group_joined' : 'group_created')
    await refreshGroups()
    await openGroup(group.id)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'De groep kon niet worden geopend.'
  } finally { busy.value = false }
}
function joinGroup() {
  let code = invite.value.trim()
  if (/^https?:\/\//i.test(code)) {
    try { code = new URL(code).pathname.split('/join/')[1]?.split('/')[0] ?? code } catch { /* server validates the code */ }
  }
  return saveGroup('/api/groups/join', { code })
}
function createGroup() { return saveGroup('/api/groups', { name: name.value.trim() }) }

</script>
