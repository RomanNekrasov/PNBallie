<template>
  <div class="colorbar">
    <div class="colorbar-top">
      <span class="colorbar-label">{{ label }}</span>
      <span class="colorbar-score">
        <span class="team-orange">Oranje {{ orange }}</span>
        <span class="team-blue">Blauw {{ blue }}</span>
      </span>
    </div>
    <div class="bar-shell">
      <div class="bar-orange" :style="{ width: orangePct }"></div>
      <div class="bar-blue" :style="{ width: bluePct }"></div>
    </div>
    <div class="colorbar-bottom">
      <span class="team-orange">{{ orangeShare }}</span>
      <span class="team-blue">{{ blueShare }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  orange: number
  blue: number
}>()

const total = computed(() => props.orange + props.blue)
const orangePct = computed(() => total.value ? `${(props.orange / total.value) * 100}%` : '50%')
const bluePct = computed(() => total.value ? `${(props.blue / total.value) * 100}%` : '50%')
const orangeShare = computed(() => total.value ? `${Math.round((props.orange / total.value) * 100)}%` : '50%')
const blueShare = computed(() => total.value ? `${Math.round((props.blue / total.value) * 100)}%` : '50%')
</script>

<style scoped>
.colorbar {
  border: 1px solid rgba(171, 133, 84, 0.28);
  border-radius: 10px;
  padding: 9px 10px;
  background: rgba(0, 0, 0, 0.18);
}

.colorbar-top,
.colorbar-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.colorbar-top {
  margin-bottom: 6px;
}

.colorbar-bottom {
  margin-top: 5px;
  font-size: 11px;
}

.colorbar-label {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(243, 230, 214, 0.58);
}

.colorbar-score {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.bar-shell {
  height: 12px;
  border-radius: 9999px;
  overflow: hidden;
  display: flex;
  background: rgba(243, 230, 214, 0.06);
}

.bar-orange {
  background: linear-gradient(90deg, rgba(232, 125, 47, 1), rgba(232, 125, 47, 0.82));
  transition: width 0.25s ease;
}

.bar-blue {
  background: linear-gradient(90deg, rgba(45, 95, 161, 0.9), rgba(45, 95, 161, 1));
  transition: width 0.25s ease;
}

.team-orange {
  color: #f0b26f;
}

.team-blue {
  color: #89b2de;
}
</style>
