<template>
  <div class="leaderboard-grid px-4 py-3">
    <span class="rank-pill" :class="rankClass">#{{ rank }}</span>
    <span class="truncate font-sport tracking-wide" :class="rank <= 3 ? 'font-bold' : ''">{{ name }}</span>
    <span class="text-sm font-mono font-medium text-[#d4a853] text-right tabular-nums">{{ elo }}</span>
    <span class="text-xs text-[#f0e6d6]/52 text-right tabular-nums">{{ wins }}W / {{ losses }}V</span>
    <span class="text-xs text-right tabular-nums font-sport font-bold" :class="winrateColor">{{ pct }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  rank: number
  name: string
  elo: number
  wins: number
  losses: number
}>()

const total = computed(() => props.wins + props.losses)
const pct = computed(() => total.value ? `${Math.round((props.wins / total.value) * 100)}%` : '-')

const rankClass = computed(() => {
  if (props.rank === 1) return 'rank-gold'
  if (props.rank === 2) return 'rank-silver'
  if (props.rank === 3) return 'rank-bronze'
  return 'rank-default'
})

const winrateColor = computed(() => {
  if (!total.value) return 'text-[#f0e6d6]/35'
  const r = props.wins / total.value
  if (r >= 0.55) return 'text-[#d4a853]'
  if (r <= 0.45) return 'text-red-300'
  return 'text-[#f0e6d6]/50'
})
</script>

<style scoped>
.leaderboard-grid {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr) 72px 94px 64px;
  gap: 8px;
  align-items: center;
}

.rank-pill {
  width: 42px;
  height: 22px;
  border-radius: 9999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: 'Barlow Condensed', system-ui, sans-serif;
  font-weight: 700;
  font-size: 12px;
  letter-spacing: 0.04em;
  border: 1px solid transparent;
}

.rank-gold {
  color: #f3d08b;
  background: rgba(232, 125, 47, 0.25);
  border-color: rgba(232, 125, 47, 0.5);
}

.rank-silver {
  color: rgba(243, 230, 214, 0.9);
  background: rgba(180, 180, 180, 0.2);
  border-color: rgba(220, 220, 220, 0.38);
}

.rank-bronze {
  color: #dfb57b;
  background: rgba(139, 90, 43, 0.25);
  border-color: rgba(180, 132, 81, 0.45);
}

.rank-default {
  color: rgba(243, 230, 214, 0.5);
  background: rgba(0, 0, 0, 0.2);
  border-color: rgba(243, 230, 214, 0.18);
}

@media (max-width: 640px) {
  .leaderboard-grid {
    grid-template-columns: 44px minmax(0, 1fr) 62px 78px 52px;
    gap: 6px;
  }

  .rank-pill {
    width: 34px;
    height: 20px;
    font-size: 11px;
  }
}
</style>
