<template>
  <main class="account-page">
    <header class="account-heading">
      <div><p class="account-kicker">{{ currentGroup?.name }}</p><h1 class="account-title">Wedstrijden beheren</h1></div>
      <div class="account-heading-actions"><RouterLink to="/stats" class="account-back-link" aria-label="Terug naar clubstatistieken">←</RouterLink><SettingsMenu /></div>
    </header>
    <p v-if="error" class="account-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="account-success" role="status">{{ notice }}</p>
    <button v-if="error" class="secondary-button" :disabled="busy" @click="reload">Lijst opnieuw laden</button>
    <section v-if="editing" class="account-panel match-editor">
      <h2>Wedstrijd wijzigen</h2>
      <form class="account-form" @submit.prevent="save">
        <div class="account-columns">
          <label>Oranje<input v-model.number="orangeScore" type="number" min="0" max="10" required /></label>
          <label>Blauw<input v-model.number="blueScore" type="number" min="0" max="10" required /></label>
          <label>Datum en tijd<input v-model="playedAt" type="datetime-local" step="1" required /></label>
          <label>Spelvorm<select v-model="formation" @change="setFormation"><option value="1v1">1v1</option><option value="2v2">2v2</option></select></label>
        </div>
        <div class="account-columns">
          <label v-for="(slot, index) in slots" :key="slot.side + slot.position">{{ slot.side === 'orange' ? 'Oranje' : 'Blauw' }} · {{ slot.position }}
            <select v-model.number="slots[index]!.player_id" required>
              <option :value="0" disabled>Kies speler</option>
              <option v-for="player in availablePlayers" :key="player.id" :value="player.id">{{ player.name }}{{ player.is_active ? '' : ' (inactief)' }}</option>
            </select>
          </label>
        </div>
        <div class="action-row"><button class="primary-button" :disabled="busy">{{ busy ? 'Opslaan…' : 'Wijzigingen opslaan' }}</button><button type="button" class="quiet-button" :disabled="busy" @click="editing = null">Annuleren</button></div>
      </form>
    </section>
    <section v-if="deleting" class="account-panel match-editor" role="region" aria-label="Verwijderen bevestigen">
      <h2>Wedstrijd verwijderen?</h2>
      <p class="account-muted">{{ names(deleting, 'orange') }} {{ deleting.orange_score }}–{{ deleting.blue_score }} {{ names(deleting, 'blue') }} · {{ formatLocalDateTime(deleting.played_at) }}</p>
      <p class="account-muted">Deze uitslag wordt definitief verwijderd. Statistieken en badges worden opnieuw berekend.</p>
      <div class="action-row"><button class="danger-button" :disabled="busy" @click="remove">Definitief verwijderen</button><button class="quiet-button" :disabled="busy" @click="deleting = null">Annuleren</button></div>
    </section>
    <p v-if="loading" class="account-notice">Wedstrijden laden…</p>
    <p v-else-if="!matches.length" class="account-notice">Geen wedstrijden.</p>
    <div v-else class="admin-list">
      <article v-for="match in matches" :key="match.id" class="admin-row match-row">
        <div class="match-summary"><strong>{{ names(match, 'orange') }} <span class="match-score">{{ match.orange_score }}–{{ match.blue_score }}</span> {{ names(match, 'blue') }}</strong><small>{{ formatLocalDateTime(match.played_at) }} · {{ match.players.length === 2 ? '1v1' : '2v2' }}</small><small>Ingevoerd door {{ match.recorded_by?.name ?? 'Onbekend' }}</small></div>
        <div class="action-row"><button class="secondary-button" :disabled="busy" @click="edit(match)">Wijzigen</button><button class="quiet-button" :disabled="busy" @click="confirmDelete(match)">Verwijderen</button></div>
      </article>
    </div>
    <nav class="match-pagination" aria-label="Wedstrijdpagina's"><button class="secondary-button" :disabled="offset === 0 || loading || busy" @click="page(-50)">Vorige</button><span>Pagina {{ offset / 50 + 1 }}</span><button class="secondary-button" :disabled="!hasMore || loading || busy" @click="page(50)">Volgende</button></nav>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import SettingsMenu from '../components/SettingsMenu.vue'
import { currentGroup } from '../auth'
import { api } from '../composables/useApi'
import { formatLocalDateTime, parseUtcTimestamp } from '../dateTime'
import type { Match, MatchPlayerEntry, Player } from '../types'
const matches = ref<Match[]>([])
const players = ref<Player[]>([])
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const offset = ref(0)
const hasMore = ref(false)
const editing = ref<Match | null>(null)
const deleting = ref<Match | null>(null)
const orangeScore = ref(10)
const blueScore = ref(0)
const playedAt = ref('')
const originalLocalTime = ref('')
const formation = ref('1v1')
const slots = ref<MatchPlayerEntry[]>([])
const availablePlayers = computed(() => players.value.filter(p => p.is_active || editing.value?.players.some(slot => slot.player_id === p.id)))
const names = (match: Match, side: string) => match.players.filter(p => p.side === side).map(p => players.value.find(player => player.id === p.player_id)?.name ?? 'Onbekende speler').join(' & ')
function localInput(value: string) {
  const date = parseUtcTimestamp(value)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
async function load() {
  loading.value = true
  try {
    const [rows, roster] = await Promise.all([api<Match[]>(`/api/matches?limit=51&offset=${offset.value}`), api<Player[]>('/api/players?include_inactive=true')])
    matches.value = rows.slice(0, 50); hasMore.value = rows.length > 50; players.value = roster
  } finally { loading.value = false }
}
function failed(cause: unknown) { error.value = cause instanceof Error ? cause.message : 'De aanvraag is mislukt.' }
async function reload() { editing.value = null; deleting.value = null; error.value = ''; try { await load() } catch (cause) { failed(cause) } }
async function page(delta: number) { offset.value += delta; await reload() }
async function focusEditor() { await nextTick(); document.querySelector<HTMLElement>('.match-editor')?.scrollIntoView({block:'start', behavior:'smooth'}); document.querySelector<HTMLElement>('.match-editor input, .match-editor button')?.focus({preventScroll:true}) }
function edit(match: Match) {
  error.value = ''; notice.value = ''; deleting.value = null; editing.value = {...match, players:match.players.map(p=>({...p}))}
  orangeScore.value = match.orange_score; blueScore.value = match.blue_score
  playedAt.value = originalLocalTime.value = localInput(match.played_at)
  formation.value = match.players.length === 2 ? '1v1' : '2v2'
  slots.value = match.players.map(p => ({...p})); void focusEditor()
}
function setFormation() {
  slots.value = (['orange','blue'] as const).flatMap(side => (formation.value === '1v1' ? ['solo'] as const : ['voor','achter'] as const).map((position, index) => ({side,position,player_id:slots.value.filter(p=>p.side===side)[index]?.player_id ?? 0})))
}
function confirmDelete(match: Match) { editing.value = null; error.value = ''; notice.value = ''; deleting.value = {...match, players:match.players.map(p=>({...p}))}; void focusEditor() }
async function save() {
  if (!editing.value || busy.value) return
  error.value = ''
  if (slots.value.some(p=>!p.player_id) || new Set(slots.value.map(p=>p.player_id)).size !== slots.value.length) { error.value='Kies voor elke positie een andere speler.'; return }
  const time = new Date(playedAt.value)
  if (!Number.isFinite(time.getTime()) || localInput(time.toISOString()) !== (playedAt.value.length === 16 ? playedAt.value + ':00' : playedAt.value)) { error.value='Dit lokale tijdstip bestaat niet. Kies een geldig tijdstip.'; return }
  busy.value = true
  try {
    await api(`/api/matches/${editing.value.id}`, {method:'PUT',body:JSON.stringify({orange_score:orangeScore.value,blue_score:blueScore.value,players:slots.value,played_at:playedAt.value === originalLocalTime.value ? editing.value.played_at : time.toISOString(),expected:editing.value})})
    editing.value=null; await load(); notice.value='Wedstrijd gewijzigd.'
  } catch (cause) { failed(cause) } finally { busy.value=false }
}
async function remove() {
  if (!deleting.value || busy.value) return
  busy.value=true; error.value=''
  try {
    await api(`/api/matches/${deleting.value.id}`, {method:'DELETE',body:JSON.stringify(deleting.value)})
    deleting.value=null
    if (matches.value.length === 1 && offset.value) offset.value-=50
    await load(); notice.value='Wedstrijd verwijderd.'
  } catch (cause) { failed(cause) } finally { busy.value=false }
}
onMounted(reload)
</script>

<style scoped>
.match-editor { margin-bottom: 24px; scroll-margin-top: 16px; }
.match-row { display:flex; justify-content:space-between; align-items:center; gap:16px; }
.match-summary { min-width:0; overflow-wrap:anywhere; }
.match-summary strong { font-size:14px; line-height:1.7; }
.match-summary small { display:block; margin-top:6px; color:#acb9ca; font-size:12px; }
.match-score { display:inline-block; color:#ffc187; white-space:nowrap; padding:0 8px; }
.match-pagination { display:flex; justify-content:center; align-items:center; gap:16px; margin-top:24px; font-size:13px; }
@media(max-width:640px) { .match-row { align-items:stretch; flex-direction:column; } }
</style>
