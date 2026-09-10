<template>
  <main class="account-page">
    <header class="account-heading">
      <div><p class="account-kicker">BEHEER · {{ currentGroup?.name }}</p><h1 class="account-title">Jouw competitie</h1><p class="account-muted">Beheer spelers, leden en uitnodigingen voor deze groep.</p></div>
      <div class="account-heading-actions"><RouterLink to="/stats" class="account-back-link" aria-label="Terug naar clubstatistieken" title="Terug naar clubstatistieken"><span aria-hidden="true">←</span></RouterLink><SettingsMenu /></div>
    </header>
    <p v-if="error" class="account-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="account-success" role="status">{{ notice }}</p>
    <p v-if="loading" class="account-notice">Beheer wordt geladen…</p>
    <template v-else>
      <div class="account-columns">
        <section class="account-panel">
          <h2>Groep</h2>
          <form class="account-form" @submit.prevent="renameGroup">
            <label>Groepsnaam<input v-model="groupName" maxlength="80" required /></label>
            <button class="secondary-button" :disabled="busy" type="submit">Naam opslaan</button>
          </form>
        </section>
        <section class="account-panel">
          <h2>Speler toevoegen</h2>
          <p class="account-muted">Een speler zonder account kan ook meedoen. Koppel later een groepslid aan het profiel.</p>
          <form class="account-form" @submit.prevent="addPlayer">
            <label>Spelersnaam<input v-model="newPlayerName" maxlength="80" required /></label>
            <button class="primary-button" :disabled="busy" type="submit">Speler toevoegen</button>
          </form>
        </section>
      </div>

      <section class="account-panel" style="margin-top:20px">
        <div class="action-row"><h2>Spelers</h2><span class="account-hint">{{ players.filter(player => player.is_active).length }} actief</span></div>
        <p class="account-muted">Deactiveren haalt een speler uit de spelerskeuze. Uitslagen en badges blijven bewaard.</p>
        <div class="admin-list">
          <form v-for="player in players" :key="player.id" class="admin-row" :class="{ inactive: !player.is_active }" @submit.prevent="savePlayer(player)">
            <div class="admin-row-head"><strong>{{ player.name }}</strong><span class="role-tag">{{ player.is_active ? 'Actief' : 'Inactief' }}</span></div>
            <div class="account-columns">
              <label class="account-label">Naam<input v-model="player.name" maxlength="80" required /></label>
              <label class="account-label">Gekoppeld groepslid
                <select v-model="player.user_id">
                  <option :value="null">Geen account gekoppeld</option>
                  <option v-for="member in members" :key="member.user_id" :value="member.user_id">{{ member.display_name }} · {{ member.email }}</option>
                </select>
              </label>
            </div>
            <div class="action-row">
              <button type="submit" class="secondary-button" :disabled="busy">Opslaan</button>
              <button type="button" :class="player.is_active ? 'quiet-button' : 'secondary-button'" :disabled="busy" @click="togglePlayer(player)">{{ player.is_active ? 'Deactiveren' : 'Activeren' }}</button>
            </div>
          </form>
        </div>
      </section>

      <section class="account-panel" style="margin-top:20px">
        <h2>Leden en rollen</h2>
        <p class="account-muted">Beheerders kunnen spelers en uitnodigingen beheren. Een groep houdt altijd minstens één beheerder.</p>
        <div class="admin-list">
          <article v-for="member in members" :key="member.user_id" class="admin-row">
            <div class="admin-row-head">
              <div><strong>{{ member.display_name }}{{ member.user_id === authUser?.id ? ' (jij)' : '' }}</strong><small>{{ member.email }}</small></div>
              <span class="role-tag">{{ member.role === 'admin' ? 'Beheerder' : 'Lid' }}</span>
            </div>
            <div class="action-row">
              <button class="secondary-button" :disabled="busy || (member.role === 'admin' && adminCount <= 1)" @click="changeRole(member)">{{ member.role === 'admin' ? 'Maak lid' : 'Maak beheerder' }}</button>
              <button class="danger-button" :disabled="busy || (member.role === 'admin' && adminCount <= 1)" @click="pendingRemove = member.user_id">Toegang intrekken</button>
            </div>
            <div v-if="pendingRemove === member.user_id" class="account-notice">
              <p>De toegang van {{ member.display_name }} intrekken? De wedstrijdhistorie blijft staan.</p>
              <div class="action-row" style="margin-top:10px">
                <button class="danger-button" :disabled="busy" @click="removeMember(member.user_id)">Ja, toegang intrekken</button>
                <button class="quiet-button" @click="pendingRemove = null">Annuleren</button>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="account-panel" style="margin-top:20px">
        <h2>Uitnodigingen</h2>
        <p class="account-muted">Maak een code en deel de link met je groep. Je kunt de uitnodiging later intrekken.</p>
        <form class="account-form" @submit.prevent="createInvite">
          <div class="account-columns">
            <label>Geldig voor<select v-model.number="inviteDays"><option :value="1">1 dag</option><option :value="7">7 dagen</option><option :value="30">30 dagen</option></select></label>
            <label>Maximaal aantal nieuwe leden<input v-model="inviteUses" type="number" min="1" max="10000" placeholder="Onbeperkt" /></label>
          </div>
          <button class="primary-button" type="submit" :disabled="busy">Uitnodiging maken</button>
        </form>
        <div v-if="createdInvite" class="account-success invite-result">
          <strong>Kopieer de code of link. Deze wordt één keer getoond.</strong>
          <code class="invite-code">{{ createdInvite.code }}</code>
          <label class="account-label">Uitnodigingslink<input :value="inviteLink" readonly @focus="($event.target as HTMLInputElement).select()" /></label>
          <div class="action-row"><button class="secondary-button" @click="copyInvite">{{ copied ? 'Gekopieerd!' : 'Kopieer link' }}</button><span>Geldig tot {{ formatLocalDateTime(createdInvite.expires_at) }}</span></div>
        </div>
        <div class="admin-list">
          <div v-for="invite in invites" :key="invite.id" class="admin-row">
            <div class="admin-row-head"><div><strong>Uitnodiging #{{ invite.id }}</strong><small>{{ invite.uses }} gebruikt{{ invite.max_uses ? ' / ' + invite.max_uses : '' }} · tot {{ formatLocalDateTime(invite.expires_at) }}</small></div><span class="role-tag">{{ inviteStatus(invite) }}</span></div>
            <button v-if="inviteStatus(invite) === 'Actief'" class="quiet-button" :disabled="busy" @click="revokeInvite(invite.id)">Uitnodiging intrekken</button>
          </div>
        </div>
        <p v-if="!invites.length" class="account-muted">Er zijn nog geen uitnodigingen.</p>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { authUser, currentGroup, isGroupAdmin, refreshGroups } from '../auth'
import { api } from '../composables/useApi'
import SettingsMenu from '../components/SettingsMenu.vue'
import { formatLocalDateTime, parseUtcTimestamp } from '../dateTime'
import type { Player } from '../types'
import { trackEvent, type AnalyticsEvent } from '../analytics'

interface Member { user_id: number; email: string; display_name: string; role: 'admin' | 'member'; player_id: number | null }
interface Invite { id: number; expires_at: string; max_uses: number | null; uses: number; revoked: boolean }
const router = useRouter()
const players = ref<Player[]>([])
const members = ref<Member[]>([])
const invites = ref<Invite[]>([])
const groupName = ref(currentGroup.value?.name ?? '')
const newPlayerName = ref('')
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const inviteDays = ref(7)
const inviteUses = ref('')
const createdInvite = ref<(Invite & { code: string }) | null>(null)
const copied = ref(false)
const pendingRemove = ref<number | null>(null)
const adminCount = computed(() => members.value.filter(member => member.role === 'admin').length)
const inviteLink = computed(() => createdInvite.value ? `${window.location.origin}/join/${encodeURIComponent(createdInvite.value.code)}` : '')

async function load() {
  const results = await Promise.all([
    api<Player[]>('/api/players?include_inactive=true'),
    api<Member[]>('/api/groups/members'),
    api<Invite[]>('/api/groups/invites'),
  ])
  ;[players.value, members.value, invites.value] = results
}
onMounted(async () => {
  try { await load() } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Beheer laden is niet gelukt.' }
  finally { loading.value = false }
})
async function mutate(action: () => Promise<unknown>, message: string, event?: AnalyticsEvent) {
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await action()
    if (event) trackEvent(event)
    await refreshGroups()
    if (!isGroupAdmin.value) { await router.replace('/groups'); return }
    await load()
    notice.value = message
  } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Opslaan is niet gelukt.' }
  finally { busy.value = false }
}
function renameGroup() { return mutate(() => api('/api/groups/current', { method: 'PATCH', body: JSON.stringify({ name: groupName.value.trim() }) }), 'Groepsnaam opgeslagen.', 'group_updated') }
function addPlayer() {
  return mutate(async () => {
    await api('/api/players', { method: 'POST', body: JSON.stringify({ name: newPlayerName.value.trim() }) })
    newPlayerName.value = ''
  }, 'Speler toegevoegd.', 'player_added')
}
function savePlayer(player: Player) { return mutate(() => api('/api/players/' + player.id, { method: 'PATCH', body: JSON.stringify({ name: player.name.trim(), user_id: player.user_id }) }), 'Speler opgeslagen.', 'player_updated') }
function togglePlayer(player: Player) { return mutate(() => api('/api/players/' + player.id, { method: 'PATCH', body: JSON.stringify({ is_active: !player.is_active }) }), player.is_active ? 'Speler gedeactiveerd. Historie blijft bewaard.' : 'Speler geactiveerd.', 'player_updated') }
function changeRole(member: Member) { return mutate(() => api('/api/groups/members/' + member.user_id, { method: 'PATCH', body: JSON.stringify({ role: member.role === 'admin' ? 'member' : 'admin' }) }), 'Rol aangepast.', 'member_updated') }
function removeMember(id: number) {
  return mutate(async () => {
    await api('/api/groups/members/' + id, { method: 'DELETE' })
    pendingRemove.value = null
  }, 'Toegang ingetrokken. Historie blijft bewaard.', 'member_removed')
}
function createInvite() {
  return mutate(async () => {
    createdInvite.value = await api<Invite & { code: string }>('/api/groups/invites', { method: 'POST', body: JSON.stringify({ expires_in_days: inviteDays.value, max_uses: inviteUses.value ? Number(inviteUses.value) : null }) })
    copied.value = false
  }, 'Uitnodiging gemaakt.', 'invite_created')
}
function revokeInvite(id: number) {
  return mutate(async () => {
    await api('/api/groups/invites/' + id, { method: 'DELETE' })
    if (createdInvite.value?.id === id) createdInvite.value = null
  }, 'Uitnodiging ingetrokken.', 'invite_revoked')
}
function inviteStatus(invite: Invite): string {
  if (invite.revoked) return 'Ingetrokken'
  if (parseUtcTimestamp(invite.expires_at).getTime() <= Date.now()) return 'Verlopen'
  if (invite.max_uses !== null && invite.uses >= invite.max_uses) return 'Vol'
  return 'Actief'
}
async function copyInvite() {
  try { await navigator.clipboard.writeText(inviteLink.value); copied.value = true }
  catch { error.value = 'Kopiëren lukt hier niet automatisch. Selecteer de link en kopieer deze.' }
}
</script>
