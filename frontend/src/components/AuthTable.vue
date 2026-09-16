<template>
  <main class="account-page auth-table-page">
    <div class="auth-table">
      <FoosballTable class="auth-table-field" stretch aria-hidden="true" focusable="false" />
      <section class="account-panel auth-table-panel"><slot /></section>
    </div>
  </main>
</template>

<script setup lang="ts">
import FoosballTable from './FoosballTable.vue'
</script>

<style>
.auth-table-page { display: grid; place-items: center; padding: 16px 8px; }
.auth-table { position: relative; display: grid; align-items: center; width: min(100%, 550px); min-height: 740px; padding: 128px 64px; }
.auth-table-field { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.auth-table-panel { position: relative; width: 100%; padding: 28px; background: #13251ff5; border-color: #668064; border-radius: 16px; box-shadow: 0 8px 28px #0005; }
.auth-table-panel .account-title { text-align: center; font-size: 46px; margin-bottom: 24px; }
.auth-table-panel h1.account-title:first-child { letter-spacing: .01em; }
.auth-table-panel > .secondary-button { width: 100%; }
.auth-table-panel input { background: #0e1b17; border-color: #53695d; }
.auth-table-panel .account-tabs { background: #0e1b17; border-color: #53695d; }
.auth-table-panel .account-tabs button.active { background: #395745; }
.auth-link { display: flex; justify-content: center; align-items: center; min-height: 44px; margin-top: 10px; color: #e0e7d7; font-size: 13px; text-underline-offset: 4px; text-decoration: underline; }
.auth-link:hover { color: #ffb575; }
@media (max-width: 640px) {
  .account-page.auth-table-page { padding: 8px 2px; }
  .auth-table { min-height: 690px; padding: 112px 11%; }
  .account-panel.auth-table-panel { padding: 24px 18px; }
  .auth-table-panel .account-title { font-size: 40px; }
}
</style>
