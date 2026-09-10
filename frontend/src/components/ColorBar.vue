<template>
  <div class="colorbar">
    <div class="colorbar-top">
      <span class="colorbar-label">{{ label }}</span>
      <span class="colorbar-score">
        <span class="team-orange">Oranje {{ orange }}</span>
        <span class="team-blue">Blauw {{ blue }}</span>
      </span>
    </div>
    <div class="bar-line" :aria-label="`${label}: ${conclusion}`">
      <div class="bar-shell" :class="{ empty: !total }">
        <div class="bar-orange" :style="{ width: orangePct }"></div>
        <div class="bar-blue" :style="{ width: bluePct }"></div>
      </div>
      <span class="leader-dot" :class="leader" :style="{ left: orangePct }" aria-hidden="true"></span>
    </div>
    <div class="colorbar-bottom">
      <span class="team-orange">{{ orangeShare }}</span>
      <span class="colorbar-conclusion">{{ conclusion }}</span>
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
const orangeShare = computed(() => total.value ? `${Math.round((props.orange / total.value) * 100)}%` : '–')
const blueShare = computed(() => total.value ? `${Math.round((props.blue / total.value) * 100)}%` : '–')
const leader = computed(() => props.orange > props.blue ? 'orange' : props.blue > props.orange ? 'blue' : 'tie')
const conclusion = computed(() => !total.value ? 'Nog geen wedstrijden' : leader.value === 'tie' ? 'Gelijke stand' : `${leader.value === 'orange' ? 'Oranje' : 'Blauw'} leidt`)
</script>

<style scoped>
.colorbar {
  border: 1px solid #303b4b;
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
  color: #aeb9c9;
}

.colorbar-score {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.bar-shell {
  height: 8px;
  border-radius: 9999px;
  overflow: hidden;
  display: flex;
  background: rgba(243, 230, 214, 0.06);
}

.bar-line { position: relative; margin: 11px 5px 9px; }
.bar-shell.empty { opacity: .25; }
.leader-dot { position: absolute; top: 50%; width: 14px; height: 14px; border-radius: 50%; border: 2px solid #17202c; transform: translate(-50%, -50%); box-shadow: 0 0 0 1px currentColor; }
.leader-dot.orange { color: #ff904f; background: #ff904f; }
.leader-dot.blue { color: #75adff; background: #75adff; }
.leader-dot.tie { color: #aeb9c9; background: #aeb9c9; }
.colorbar-conclusion { color: #aeb9c9; text-align: center; font-size: 10px; }

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
