<template>
  <main class="account-page">
    <section class="account-panel">
      <h1 class="account-title">Bevestig je e-mailadres</h1>
      <template v-if="!authUser">
        <p>Log in met het account waarvoor je de mail hebt aangevraagd.</p>
        <form class="account-form" @submit.prevent="signIn">
          <label>E-mailadres<input v-model="email" type="email" autocomplete="email" required /></label>
          <label>Wachtwoord<input v-model="password" type="password" autocomplete="current-password" required /></label>
          <button class="primary-button" :disabled="busy">Inloggen</button>
        </form>
      </template>
      <template v-else-if="authUser.email_verified">
        <p>Je e-mailadres is bevestigd.</p>
        <button class="primary-button" @click="continueToApp">Doorgaan</button>
      </template>
      <template v-else>
        <p>{{ authUser.email }}</p>
        <p v-if="token">Bevestig dat dit jouw e-mailadres is.</p>
        <p v-else-if="verificationSent">Open de link in je mail. Controleer ook je spammap.</p>
        <p v-else-if="verificationSent === false" class="account-error">Je account is aangemaakt, maar de mail kon niet worden verstuurd. Probeer het over een minuut opnieuw.</p>
        <p v-else>Vraag een mail aan om je e-mailadres te bevestigen.</p>
        <button v-if="token" class="primary-button" :disabled="busy" @click="confirm">E-mailadres bevestigen</button>
        <button class="secondary-button" :disabled="busy || cooldown > 0" @click="resend">{{ cooldown > 0 ? `Opnieuw versturen over ${cooldown}s` : 'Verificatiemail versturen' }}</button>
      </template>
      <p v-if="error" class="account-error" role="alert">{{ error }}</p>
      <button v-if="authUser" class="secondary-button" :disabled="busy" @click="signOut">Uitloggen</button>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authUser, confirmVerification, login, logout, requestVerification, safeReturnPath, verificationSent } from '../auth'

const route = useRoute()
const router = useRouter()
const supplied = new URLSearchParams(route.hash.slice(1)).get('token') ?? ''
const token = ref(/^[A-Za-z0-9_-]{43}$/.test(supplied) ? supplied : '')
// Keep the token only in component memory, never in storage or a return URL.
if (route.hash) void router.replace({ path: route.path, query: route.query, hash: '' })
const nextPath = ref(safeReturnPath(route.query.redirect))
const email = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)
const cooldown = ref(verificationSent.value !== null ? 60 : 0)
const timer = setInterval(() => { cooldown.value = Math.max(0, cooldown.value - 1) }, 1000)
onUnmounted(() => clearInterval(timer))

async function run(action: () => Promise<void>) {
  busy.value = true
  error.value = ''
  try { await action() } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Probeer het opnieuw.' }
  finally { busy.value = false }
}
async function signIn() { await run(async () => { await login(email.value.trim(), password.value); password.value = '' }) }
async function confirm() { await run(async () => { nextPath.value = await confirmVerification(token.value); token.value = '' }) }
async function resend() { await run(async () => { await requestVerification(nextPath.value); cooldown.value = 60; token.value = '' }) }
async function signOut() { await run(async () => { await logout(); await router.replace('/login') }) }
async function continueToApp() {
  const target = nextPath.value
  await router.replace(target.startsWith('/verify-email') ? '/' : target)
}
</script>
