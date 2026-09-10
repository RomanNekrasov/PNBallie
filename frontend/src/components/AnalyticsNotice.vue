<template>
  <details v-if="analyticsEnabled" class="analytics-notice">
    <summary>Over gebruiksstatistieken</summary>
    <p>We meten schermgebruik en acties met onze eigen Umami, zonder namen, foto's of uitslagen. Je IP-adres geeft een globale locatie, geen GPS-locatie. We respecteren Do Not Track in je browser. Geen sessieopnames of volgcookies.</p>
  </details>
</template>

<script setup lang="ts">
import { analyticsEnabled } from '../analytics'
</script>

<style scoped>
.analytics-notice { padding: 10px; color: #a7b7cb; font: 400 11px/1.5 system-ui, sans-serif; }
.analytics-notice summary { cursor: pointer; }
.analytics-notice p { margin-top: 8px; }
</style>
