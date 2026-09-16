<template>
  <AuthTable>
    <h1 class="account-title">PNBallie</h1>
    <p v-if="route.query.redirect?.toString().startsWith('/join/')" class="account-notice">Je bent uitgenodigd voor een groep. Log in of maak een account om mee te doen.</p>
    <div v-if="authProviders?.registration_enabled" class="account-tabs" aria-label="Accountkeuze">
      <button :aria-pressed="!creating" :class="{ active: !creating }" @click="creating = false">Inloggen</button>
      <button :aria-pressed="creating" :class="{ active: creating }" @click="creating = true">Account maken</button>
    </div>
    <form class="account-form" @submit.prevent="submit">
      <label v-if="creating">Je naam<input v-model="displayName" autocomplete="name" required maxlength="80" /></label>
      <label>E-mailadres<input v-model="email" type="email" autocomplete="email" required maxlength="254" /></label>
      <label>Wachtwoord<input v-model="password" type="password" :autocomplete="creating ? 'new-password' : 'current-password'" :minlength="creating ? 12 : undefined" maxlength="1024" required /></label>
      <p v-if="creating" class="account-hint">Kies een wachtwoord van minimaal 12 tekens.</p>
      <p v-if="error" class="account-error" role="alert">{{ error }}</p>
      <button class="primary-button" type="submit" :disabled="busy">{{ busy ? 'Even geduld…' : creating ? 'Account maken' : 'Inloggen' }}</button>
    </form>
    <RouterLink v-if="!creating && authProviders?.password_reset_enabled" to="/forgot-password" class="auth-link">Wachtwoord vergeten?</RouterLink>
    <template v-if="authProviders?.oidc">
      <div class="account-divider">of</div>
      <a :href="oidcLoginUrl" class="secondary-button">Doorgaan met {{ authProviders.oidc.name }}</a>
    </template>
  </AuthTable>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AuthTable from '../components/AuthTable.vue'
import { useRoute, useRouter } from 'vue-router'
import { authProviders, login, register, safeReturnPath } from '../auth'

const route = useRoute()
const router = useRouter()
const creating = ref(false)
const displayName = ref('')
const email = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')
const oidcLoginUrl = computed(() => `${authProviders.value?.oidc?.login_url ?? ''}?next=${encodeURIComponent(safeReturnPath(route.query.redirect))}`)

async function submit() {
  busy.value = true
  error.value = ''
  try {
    if (creating.value) await register(email.value.trim(), password.value, displayName.value.trim(), safeReturnPath(route.query.redirect))
    else await login(email.value.trim(), password.value)
    password.value = ''
    await router.replace(safeReturnPath(route.query.redirect))
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Inloggen is niet gelukt.'
  } finally { busy.value = false }
}
</script>
