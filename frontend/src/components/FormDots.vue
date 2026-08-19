<template>
  <div class="form-dots" :aria-label="ariaLabel">
    <span
      v-for="(result, index) in results"
      :key="index"
      class="form-dot"
      :class="result === 'W' ? 'form-win' : 'form-loss'"
      :title="result === 'W' ? 'Winst' : 'Verlies'"
    >{{ result }}</span>
    <span v-if="results.length === 0" class="form-empty">–</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { MatchResult } from '../types'

const props = defineProps<{ results: MatchResult[] }>()

const ariaLabel = computed(() => {
  if (!props.results.length) return 'Geen recente wedstrijden'
  return `Recente vorm: ${props.results.map(result => result === 'W' ? 'winst' : 'verlies').join(', ')}`
})
</script>

<style scoped>
.form-dots {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.form-dot {
  width: 23px;
  height: 23px;
  border-radius: 7px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font: 800 11px/1 'Barlow Condensed', system-ui, sans-serif;
  border: 1px solid transparent;
}

.form-win {
  color: #061a10;
  background: #58e899;
  border-color: #8ff2ba;
  box-shadow: 0 0 14px rgba(88, 232, 153, 0.22);
}

.form-loss {
  color: #29090b;
  background: #ff6874;
  border-color: #ff9ca4;
}

.form-empty {
  color: rgba(255, 255, 255, 0.4);
}
</style>
