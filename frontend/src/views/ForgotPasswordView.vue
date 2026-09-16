<template>
  <AuthTable>
    <h1 class="account-title">Wachtwoord vergeten</h1>
    <p v-if="message" class="account-success" role="status">{{ message }}</p>
    <form v-else class="account-form" @submit.prevent="submit">
      <label>E-mailadres<input v-model="email" type="email" autocomplete="email" required maxlength="254" /></label>
      <p v-if="error" class="account-error" role="alert">{{ error }}</p>
      <button class="primary-button" :disabled="busy">{{ busy ? 'Even geduld…' : 'Stuur herstellink' }}</button>
    </form>
    <RouterLink to="/login" class="auth-link">Terug naar inloggen</RouterLink>
  </AuthTable>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AuthTable from '../components/AuthTable.vue'
import { requestPasswordReset } from '../auth'
const email = ref('')
const busy = ref(false)
const error = ref('')
const message = ref('')
async function submit() {
  busy.value = true
  error.value = ''
  try { message.value = await requestPasswordReset(email.value.trim()) }
  catch (cause) { error.value = cause instanceof Error ? cause.message : 'Probeer het later opnieuw.' }
  finally { busy.value = false }
}
</script>
