<template>
  <section class="account-panel table-settings-panel">
    <h2>Jullie tafel</h2>
    <p class="account-muted">Stel de kleuren en de plek van de scores in zoals jullie voetbaltafel er in het echt uitziet. Deze instellingen gelden voor iedereen in de groep.</p>
    <form class="table-settings-layout" @submit.prevent="save">
      <div class="account-form">
        <label>Kleur team met het doel bovenaan
          <select v-model="draft.blue_color" :disabled="saving">
            <option v-for="(color, key) in teamColors" :key="key" :value="key" :disabled="key === draft.orange_color">{{ color.label }}</option>
          </select>
        </label>
        <label>Kleur team met het doel onderaan
          <select v-model="draft.orange_color" :disabled="saving">
            <option v-for="(color, key) in teamColors" :key="key" :value="key" :disabled="key === draft.blue_color">{{ color.label }}</option>
          </select>
        </label>
        <div class="table-color-inputs">
          <label>Speelveld<input v-model="draft.field_color" type="color" :disabled="saving" /></label>
          <label>Tafelrand<input v-model="draft.rim_color" type="color" :disabled="saving" /></label>
        </div>
        <label>Plek van de scores
          <select v-model="draft.score_position" :disabled="saving">
            <option value="own_goal">Bij het eigen doel</option>
            <option value="opponent_goal">Bij het doel van de tegenstander</option>
          </select>
        </label>
        <p class="account-hint">Bij sommige tafels houd je de score aan de overkant bij. Kies de plek die jullie gewend zijn; de score blijft bij hetzelfde team horen.</p>
        <p v-if="error" class="account-error" role="alert">{{ error }}</p>
        <p v-if="saved" class="account-success" role="status">Tafelinstellingen opgeslagen voor je groep.</p>
        <div class="action-row">
          <button type="submit" class="primary-button" :disabled="saving">{{ saving ? 'Opslaan…' : 'Tafel opslaan' }}</button>
          <button type="button" class="quiet-button" :disabled="saving" @click="reset">Standaardinstellingen</button>
        </div>
      </div>
      <figure class="table-preview" :style="tableVariables(draft)">
        <figcaption>Voorbeeld van jullie tafel</figcaption>
        <div class="table-preview-field" role="img" :aria-label="`Boven: doel van ${teamColors[draft.blue_color].label}, score van ${teamColors[draft[`${topSide}_color`]].label}. Onder: doel van ${teamColors[draft.orange_color].label}.`">
          <FoosballTable />
          <div v-for="side in (['orange', 'blue'] as const)" :key="side" class="table-preview-score" :class="side === topSide ? 'score-top' : 'score-bottom'" :style="{ background: `var(--team-${side}-dark)`, borderColor: `var(--team-${side})` }">
            {{ teamColors[draft[`${side}_color`]].label }} · 0
          </div>
        </div>
      </figure>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { currentGroup, groups } from '../auth'
import { api } from '../composables/useApi'
import { defaultTableSettings, scoreSideAtTop, tableVariables, teamColors } from '../tableSettings'
import FoosballTable from './FoosballTable.vue'
import type { Group } from '../auth'

const draft = ref({ ...defaultTableSettings, ...currentGroup.value?.table_settings })
const saving = ref(false)
const error = ref('')
const saved = ref(false)
const topSide = computed(() => scoreSideAtTop(draft.value))
watch(draft, () => { saved.value = false }, { deep: true })
function reset() { draft.value = { ...defaultTableSettings } }
async function save() {
  saving.value = true
  error.value = ''
  saved.value = false
  try {
    const updated = await api<Group>('/api/groups/current/table', { method: 'PUT', body: JSON.stringify(draft.value) })
    groups.value = groups.value.map(group => group.id === updated.id ? updated : group)
    saved.value = true
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'Tafel opslaan is niet gelukt.'
  } finally { saving.value = false }
}
</script>

<style scoped>
.table-settings-panel { margin-top: 20px; }
.table-settings-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(180px, 260px); gap: 24px; align-items: start; }
.table-color-inputs { display: flex; gap: 20px; }
.table-color-inputs input { display: block; width: 72px; height: 44px; padding: 3px; cursor: pointer; }
.table-preview { margin: 16px 0 0; padding: 12px; border: 1px solid #465469; border-radius: 16px; background: #1a1510; }
.table-preview figcaption { text-align: center; color: #c0c9d6; font-size: 12px; margin-bottom: 16px; }
.table-preview-field { position: relative; aspect-ratio: 4 / 7; }
.table-preview-score { position: absolute; left: 50%; transform: translateX(-50%); padding: 5px 10px; border: 1px solid; border-radius: 8px; color: white; font-size: 12px; font-weight: 700; white-space: nowrap; }
.score-top { top: 0; }
.score-bottom { bottom: 0; }
@media (max-width: 600px) { .table-settings-layout { grid-template-columns: 1fr; } .table-preview { width: 220px; justify-self: center; } }
</style>
