<template>
  <main class="account-page">
    <header class="account-heading">
      <div><p class="account-kicker">{{ currentGroup?.name }}</p><h1 class="account-title">Mijn profiel</h1></div>
      <div class="account-heading-actions"><RouterLink to="/stats" class="account-back-link" aria-label="Terug naar clubstatistieken" title="Terug naar clubstatistieken"><span aria-hidden="true">←</span></RouterLink><SettingsMenu /></div>
    </header>
    <p v-if="error" class="account-error" role="alert">{{ error }}</p>
    <p v-if="notice" class="account-success" role="status">{{ notice }}</p>
    <p v-if="loading" class="account-notice">Je profiel wordt geladen…</p>
    <div v-else-if="player" class="account-columns">
      <div class="account-stack">
        <section class="account-panel">
          <h2>{{ player.name }}</h2>
          <div class="profile-preview">
            <div class="avatar-checker"><img v-if="avatarUrl" :src="avatarUrl" :alt="'Avatar van ' + player.name" /><span v-else>{{ playerInitials(player.name) }}</span></div>
            <div><p class="account-kicker">{{ currentGroup?.role === 'admin' ? 'BEHEERDER' : 'SPELER' }}</p><p class="account-muted">{{ authUser?.email }}</p></div>
          </div>
          <form class="account-form" @submit.prevent="saveProfile">
            <label>Spelersnaam in deze groep<input v-model="name" maxlength="80" required /></label>
            <button type="submit" class="primary-button" :disabled="saving">Naam opslaan</button>
          </form>
        </section>
        <section class="account-panel">
          <h2>Badges</h2>
          <p class="account-muted">Badges blijven staan als je winreeks stopt.</p>
          <PlayerBadges :badges="badges" />
          <RouterLink class="quiet-button" style="margin-top:18px" to="/stats">Bekijk je statistieken</RouterLink>
        </section>
        <section v-if="authUser?.has_password" class="account-panel">
          <h2>Wachtwoord wijzigen</h2>
          <p class="account-muted">Na het wijzigen worden je andere sessies uitgelogd.</p>
          <form class="account-form" @submit.prevent="updatePassword">
            <label>Huidig wachtwoord<input v-model="currentPassword" type="password" autocomplete="current-password" required maxlength="1024" /></label>
            <label>Nieuw wachtwoord<input v-model="newPassword" type="password" autocomplete="new-password" minlength="12" maxlength="1024" required /></label>
            <label>Herhaal nieuw wachtwoord<input v-model="repeatPassword" type="password" autocomplete="new-password" minlength="12" maxlength="1024" required /></label>
            <button class="secondary-button" type="submit" :disabled="saving">Wachtwoord opslaan</button>
          </form>
        </section>
      </div>
      <section class="account-panel">
        <h2>Avatar</h2>
        <p class="account-muted">Upload een duidelijke gezichtsfoto voor een cartoonavatar met transparante achtergrond.</p>
        <div v-if="job" class="job-status" role="status" aria-live="polite">
          <strong>{{ statusLabel(job.status) }}</strong>
          <small v-if="jobActive">Je kunt deze pagina sluiten en later terugkomen.</small>
          <small v-if="jobActive && job.provider === 'local'">Dit duurt circa 25–40 minuten, plus eventuele wachttijd.</small>
          <small v-if="jobActive && requestAge">{{ requestAge }}</small>
          <small v-if="job.status === 'succeeded'">Je nieuwe avatar wordt bij je wedstrijden en statistieken gebruikt.</small>
          <small v-if="job.status === 'failed' && requestTimestamp">Aangevraagd op <time :datetime="requestTimestamp">{{ formatLocalDateTime(job.created_at) }}</time>.</small>
          <small v-if="job.status === 'failed' && (config?.local_available || config?.openai_available)">Kies opnieuw een foto om een nieuwe aanvraag te starten.</small>
          <details v-if="job.error && job.status === 'failed'">
            <summary>Details vorige aanvraag</summary>
            <small>{{ job.error }}</small>
          </details>
          <small v-if="job.error && job.status === 'queued'">Wachten op een nieuwe poging: {{ job.error }}</small>
          <small v-if="pollError" class="account-error" role="alert">{{ pollError }} De status wordt opnieuw opgehaald.</small>
          <small v-if="jobActive || job.status === 'cancelled'">Na annuleren wordt deze avatar niet opgeslagen. De verwerking kan nog doorlopen en een volgende aanvraag vertragen.</small>
          <button v-if="jobActive" class="quiet-button" :disabled="saving" @click="cancelJob">Aanvraag annuleren</button>
        </div>
        <p v-if="config && !config.local_available && !config.openai_available" class="account-notice">Avatars maken is momenteel niet beschikbaar.</p>
        <form v-else-if="config" class="account-form" @submit.prevent="upload">
          <label>Foto (PNG, JPEG of WebP; maximaal {{ Math.round(config.max_upload_bytes / 1024 / 1024) }} MB)<input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp" :disabled="jobActive || saving" @change="choosePhoto" /></label>
          <img v-if="previewUrl" :src="previewUrl" alt="Geselecteerde foto" class="upload-preview" />
          <label>Verwerking<select v-model="provider" :disabled="jobActive || saving"><option v-if="config.local_available" value="local">Eigen server</option><option v-if="config.openai_available" value="openai">GPT via OpenAI</option></select></label>
          <label v-if="provider === 'openai'" class="checkbox-label"><input v-model="cloudConsent" type="checkbox" required /><span>Ik geef toestemming om deze foto naar OpenAI te sturen voor mijn avatar.</span></label>
          <p class="account-hint">De originele upload wordt verwijderd nadat de aanvraag is afgerond. Je avatar blijft bij je profiel bewaard.</p>
          <button type="submit" class="primary-button" :disabled="!photo || jobActive || saving || (provider === 'openai' && !cloudConsent)">{{ saving ? 'Even geduld…' : 'Avatar laten maken' }}</button>
        </form>
      </section>
    </div>
    <p v-else-if="!loading" class="account-notice">Er is nog geen spelersprofiel aan je account gekoppeld. Vraag je groepsbeheerder om de koppeling te maken.</p>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { authUser, changePassword, currentGroup, refreshGroups } from '../auth'
import { api } from '../composables/useApi'
import { useStats } from '../composables/useStats'
import PlayerBadges from '../components/PlayerBadges.vue'
import SettingsMenu from '../components/SettingsMenu.vue'
import { playerAvatar, playerInitials } from '../playerAvatar'
import { formatLocalDateTime, parseUtcTimestamp } from '../dateTime'
import type { Player } from '../types'
import { trackEvent } from '../analytics'

interface AvatarConfig { local_available: boolean; openai_available: boolean; max_upload_bytes: number }
interface AvatarJob { id: string; status: 'queued' | 'processing' | 'succeeded' | 'failed' | 'cancelled'; provider: 'local' | 'openai'; created_at: string; error: string | null; avatar_url: string | null }
const player = ref<Player | null>(null)
const name = ref('')
const config = ref<AvatarConfig | null>(null)
const job = ref<AvatarJob | null>(null)
const photo = ref<File | null>(null)
const previewUrl = ref('')
const provider = ref<'local' | 'openai'>('local')
const cloudConsent = ref(false)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const pollError = ref('')
const notice = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const currentPassword = ref('')
const newPassword = ref('')
const repeatPassword = ref('')
const { stats, fetchStats } = useStats()
const avatarUrl = computed(() => playerAvatar(player.value?.name, player.value?.avatar_url))
const badges = computed(() => stats.value?.players.find(entry => entry.player_id === player.value?.id)?.badges ?? [])
const jobActive = computed(() => job.value?.status === 'queued' || job.value?.status === 'processing')
const now = ref(Date.now())
const requestTimestamp = computed(() => {
  if (!job.value?.created_at) return null
  const created = parseUtcTimestamp(job.value.created_at)
  return Number.isFinite(created.getTime()) ? created.toISOString() : null
})
const requestAge = computed(() => {
  if (!job.value?.created_at) return ''
  const created = parseUtcTimestamp(job.value.created_at).getTime()
  if (!Number.isFinite(created)) return ''
  const minutes = Math.max(0, Math.floor((now.value - created) / 60_000))
  return minutes < 1 ? 'Minder dan een minuut geleden aangevraagd.' : `${minutes} ${minutes === 1 ? 'minuut' : 'minuten'} geleden aangevraagd.`
})
let timer: ReturnType<typeof setTimeout> | undefined
let ageTimer: ReturnType<typeof setInterval> | undefined
let active = true
let jobRequestVersion = 0
watch(provider, () => { cloudConsent.value = false })
watch(job, (next, previous) => {
  if (next && previous?.id === next.id && ['queued', 'processing'].includes(previous.status)
    && ['succeeded', 'failed', 'cancelled'].includes(next.status)) {
    trackEvent('avatar_outcome', { provider: next.provider, outcome: next.status })
  }
})

function statusLabel(status: AvatarJob['status']) {
  return { queued: 'In de wachtrij', processing: 'Je avatar wordt gemaakt', succeeded: 'Je avatar is klaar!', failed: 'Vorige aanvraag mislukt', cancelled: 'Aanvraag geannuleerd' }[status]
}
function clearPhoto() {
  photo.value = null
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
  if (fileInput.value) fileInput.value.value = ''
}
function choosePhoto(event: Event) {
  const input = event.target as HTMLInputElement
  const selected = input.files?.[0]
  clearPhoto()
  if (!selected) return
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(selected.type)) { error.value = 'Kies een PNG-, JPEG- of WebP-afbeelding.'; return }
  if (selected.size > (config.value?.max_upload_bytes ?? 8 * 1024 * 1024)) { error.value = 'De foto is te groot. Kies een foto van maximaal 8 MB.'; return }
  error.value = ''
  photo.value = selected
  previewUrl.value = URL.createObjectURL(selected)
}
function schedulePoll() {
  clearTimeout(timer)
  if (active && jobActive.value) timer = setTimeout(() => { void poll() }, 5000)
}
async function poll() {
  if (!active || !job.value) return
  const version = jobRequestVersion
  const jobId = job.value.id
  try {
    const result = await api<AvatarJob>('/api/avatars/jobs/' + jobId)
    if (!active || version !== jobRequestVersion || job.value?.id !== jobId) return
    job.value = result
    pollError.value = ''
    if (result.status === 'succeeded' && player.value) {
      player.value.avatar_url = result.avatar_url
      notice.value = 'Je nieuwe avatar is opgeslagen.'
    }
  } catch (cause) {
    if (active && version === jobRequestVersion) pollError.value = cause instanceof Error ? cause.message : 'Status ophalen is niet gelukt.'
  } finally { if (version === jobRequestVersion) schedulePoll() }
}
onMounted(async () => {
  ageTimer = setInterval(() => { now.value = Date.now() }, 30_000)
  try {
    const profile = await api<Player>('/api/players/me')
    if (!active) return
    player.value = profile
    name.value = profile.name
    void fetchStats()
    const [settings, latest] = await Promise.all([api<AvatarConfig>('/api/avatars/config'), api<AvatarJob | null>('/api/avatars/me/latest')])
    if (!active) return
    config.value = settings
    provider.value = settings.local_available ? 'local' : 'openai'
    job.value = latest
    schedulePoll()
  } catch (cause) { if (active) error.value = cause instanceof Error ? cause.message : 'Profiel laden is niet gelukt.' }
  finally { if (active) loading.value = false }
})
onUnmounted(() => { active = false; jobRequestVersion++; clearTimeout(timer); clearInterval(ageTimer); clearPhoto() })
async function saveProfile() {
  saving.value = true
  error.value = ''
  try {
    player.value = await api<Player>('/api/players/me', { method: 'PATCH', body: JSON.stringify({ name: name.value.trim() }) })
    trackEvent('profile_saved')
    await refreshGroups()
    notice.value = 'Je spelersnaam is opgeslagen.'
  } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Opslaan is niet gelukt.' }
  finally { saving.value = false }
}
async function upload() {
  if (!photo.value || jobActive.value || saving.value || (provider.value === 'openai' && !cloudConsent.value)) return
  const version = ++jobRequestVersion
  clearTimeout(timer)
  saving.value = true
  error.value = ''
  notice.value = ''
  pollError.value = ''
  try {
    const result = await api<AvatarJob>(`/api/avatars/me/jobs?provider=${provider.value}&cloud_consent=${cloudConsent.value}`, {
      method: 'POST', headers: { 'Content-Type': photo.value.type }, body: photo.value,
    })
    if (!active || version !== jobRequestVersion) return
    job.value = result
    clearPhoto()
    trackEvent('avatar_queued', { provider: result.provider })
    schedulePoll()
  } catch (cause) { if (active && version === jobRequestVersion) error.value = cause instanceof Error ? cause.message : 'Uploaden is niet gelukt.' }
  finally { if (active && version === jobRequestVersion) saving.value = false }
}
async function cancelJob() {
  if (!job.value || saving.value) return
  const jobId = job.value.id
  const version = ++jobRequestVersion
  clearTimeout(timer)
  saving.value = true
  error.value = ''
  pollError.value = ''
  try {
    const result = await api<AvatarJob>('/api/avatars/jobs/' + jobId, { method: 'DELETE' })
    if (!active || version !== jobRequestVersion) return
    job.value = result
    if (result.status === 'succeeded' && player.value) player.value.avatar_url = result.avatar_url
  } catch (cause) {
    if (active && version === jobRequestVersion) {
      error.value = cause instanceof Error ? cause.message : 'Annuleren is niet gelukt.'
      schedulePoll()
    }
  } finally { if (active && version === jobRequestVersion) saving.value = false }
}
async function updatePassword() {
  error.value = ''
  if (newPassword.value !== repeatPassword.value) { error.value = 'De nieuwe wachtwoorden zijn niet gelijk.'; return }
  saving.value = true
  try {
    await changePassword(currentPassword.value, newPassword.value)
    currentPassword.value = newPassword.value = repeatPassword.value = ''
    notice.value = 'Wachtwoord gewijzigd. Andere sessies zijn uitgelogd.'
  } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Wachtwoord wijzigen is niet gelukt.' }
  finally { saving.value = false }
}
</script>
