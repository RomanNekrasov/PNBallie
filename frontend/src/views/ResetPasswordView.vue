<template>
  <AuthTable>
    <h1 class="account-title">Nieuw wachtwoord</h1>
    <template v-if="done">
      <p class="account-success" role="status">Je wachtwoord is gewijzigd. Log opnieuw in.</p>
      <RouterLink to="/login" class="secondary-button">Inloggen</RouterLink>
    </template>
    <template v-else-if="!token">
      <p class="account-notice">Open de herstellink uit je mail of vraag een nieuwe aan.</p>
      <RouterLink to="/forgot-password" class="auth-link">Nieuwe herstellink</RouterLink>
    </template>
    <template v-else>
      <form class="account-form" @submit.prevent="submit">
        <label>Nieuw wachtwoord<input v-model="password" type="password" autocomplete="new-password" minlength="12" maxlength="1024" required /></label>
        <label>Herhaal wachtwoord<input v-model="confirmation" type="password" autocomplete="new-password" minlength="12" maxlength="1024" required /></label>
        <p class="account-hint">Minimaal 12 tekens.</p>
        <p v-if="error" class="account-error" role="alert">{{ error }}</p>
        <button class="primary-button" :disabled="busy">{{ busy ? 'Even geduld…' : 'Wachtwoord opslaan' }}</button>
      </form>
      <RouterLink to="/forgot-password" class="auth-link">Nieuwe herstellink</RouterLink>
    </template>
  </AuthTable>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthTable from '../components/AuthTable.vue'
import { resetPassword } from '../auth'
const route = useRoute()
const router = useRouter()
const candidate = new URLSearchParams(route.hash.slice(1)).get('token') ?? ''
const token = ref(/^[A-Za-z0-9_-]{43}$/.test(candidate) ? candidate : '')
const password = ref('')
const confirmation = ref('')
const error = ref('')
const busy = ref(false)
const done = ref(false)
onMounted(async () => { if (route.hash) await router.replace({ path: '/reset-password', hash: '' }) })
async function submit() {
  error.value = ''
  if (password.value !== confirmation.value) { error.value = 'De wachtwoorden zijn niet gelijk.'; return }
  busy.value = true
  try {
    await resetPassword(token.value, password.value)
    password.value = ''; confirmation.value = ''; token.value = ''; done.value = true
  } catch (cause) { error.value = cause instanceof Error ? cause.message : 'Opslaan is niet gelukt.' }
  finally { busy.value = false }
}
</script>
