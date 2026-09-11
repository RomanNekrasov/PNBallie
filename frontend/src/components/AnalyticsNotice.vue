<template>
  <details v-if="analyticsEnabled" class="analytics-notice">
    <summary>Over gebruiksstatistieken</summary>
    <p>We meten schermgebruik en acties op onze eigen server, zonder namen, foto's of uitslagen. Je IP-adres geeft een globale locatie, geen GPS-locatie. Geen sessieopnames of volgcookies. We respecteren Do Not Track en Global Privacy Control in je browser.</p>
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
