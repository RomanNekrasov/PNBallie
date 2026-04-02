<template>
  <div class="w-full min-h-dvh bg-[#1a1a2e] text-white">
    <div class="max-w-[960px] mx-auto px-6 py-8">
      <!-- Header -->
      <div class="flex items-center gap-3 mb-8">
        <button @click="router.push('/')" class="glass-btn shrink-0">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 12H5" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
        </button>
        <h1 class="text-2xl font-bold">Statistieken</h1>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="text-center text-white/50 py-16">Laden...</div>

      <!-- Error -->
      <div v-else-if="error" class="text-center text-red-400 py-16">{{ error }}</div>

      <template v-else-if="stats">
        <!-- Tabs -->
        <div class="flex gap-2 mb-8">
          <button
            v-for="tab in ['Spelers', 'Globaal'] as const"
            :key="tab"
            @click="activeTab = tab"
            class="px-5 py-2.5 rounded-lg text-sm font-medium transition-colors"
            :class="activeTab === tab ? 'bg-white/20 text-white' : 'bg-white/5 text-white/50 hover:bg-white/10'"
          >
            {{ tab }}
          </button>
        </div>

        <!-- Spelers tab -->
        <div v-if="activeTab === 'Spelers'">
          <div v-if="stats.players.length === 0" class="text-white/50 text-center py-12">
            Nog geen spelers
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div
              v-for="p in stats.players"
              :key="p.player_id"
              class="glass-card"
            >
              <button
                @click="togglePlayer(p.player_id)"
                class="w-full flex items-center justify-between p-4"
              >
                <div class="flex items-center gap-3">
                  <span class="text-lg font-bold">{{ p.name }}</span>
                  <span class="text-xs text-white/40">{{ p.wins }}W / {{ p.losses }}L</span>
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium" :class="winrateColor(p.wins, p.losses)">
                    {{ winrate(p.wins, p.losses) }}
                  </span>
                  <svg
                    xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
                    fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
                    class="transition-transform" :class="expanded.has(p.player_id) ? 'rotate-180' : ''"
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </div>
              </button>

              <div v-if="expanded.has(p.player_id)" class="px-4 pb-4 space-y-2 text-sm">
                <div class="grid grid-cols-2 gap-2">
                  <StatItem label="1v1" :value="`${p.wins_1v1}W / ${p.losses_1v1}L`" />
                  <StatItem label="2v2" :value="`${p.wins_2v2}W / ${p.losses_2v2}L`" />
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <StatItem label="Winstreak" :value="`${p.current_winstreak} (max ${p.longest_winstreak})`" />
                  <StatItem label="Losestreak" :value="`${p.current_losestreak} (max ${p.longest_losestreak})`" />
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <StatItem label="Oranje" :value="formatPct(p.winrate_orange)" :sub="deltaText(p.color_delta)" />
                  <StatItem label="Blauw" :value="formatPct(p.winrate_blue)" />
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <StatItem label="Voor" :value="formatPct(p.winrate_voor)" :sub="deltaText(p.position_delta)" />
                  <StatItem label="Achter" :value="formatPct(p.winrate_achter)" />
                </div>
                <StatItem label="Grootste overwinning" :value="`10-${10 - p.biggest_victory_margin}`" />
              </div>
            </div>
          </div>
        </div>

        <!-- Globaal tab -->
        <div v-if="activeTab === 'Globaal'">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <!-- Left column -->
            <div class="space-y-4">
              <div class="glass-card p-5">
                <h3 class="text-sm font-semibold text-white/60 mb-3">Overzicht</h3>
                <div class="text-3xl font-bold mb-4">{{ stats.global.total_matches }} wedstrijden</div>
                <div class="space-y-3">
                  <ColorBar label="Totaal" :orange="stats.global.orange_wins" :blue="stats.global.blue_wins" />
                  <ColorBar label="1v1" :orange="stats.global.orange_wins_1v1" :blue="stats.global.blue_wins_1v1" />
                  <ColorBar label="2v2" :orange="stats.global.orange_wins_2v2" :blue="stats.global.blue_wins_2v2" />
                </div>
              </div>

              <div class="glass-card p-5">
                <h3 class="text-sm font-semibold text-white/60 mb-3">Kleur streaks</h3>
                <div class="grid grid-cols-2 gap-2">
                  <StatItem label="Oranje actief" :value="String(stats.global.current_orange_streak)" />
                  <StatItem label="Oranje langst" :value="String(stats.global.longest_orange_streak)" />
                  <StatItem label="Blauw actief" :value="String(stats.global.current_blue_streak)" />
                  <StatItem label="Blauw langst" :value="String(stats.global.longest_blue_streak)" />
                </div>
              </div>
            </div>

            <!-- Right column -->
            <div class="space-y-4">
              <div class="glass-card p-5">
                <h3 class="text-sm font-semibold text-white/60 mb-3">Tijdstip</h3>
                <div class="grid grid-cols-2 gap-2">
                  <StatItem label="Lunch (< 14:00)" :value="String(stats.global.lunch_matches)" />
                  <StatItem label="Middag (≥ 14:00)" :value="String(stats.global.middag_matches)" />
                </div>
              </div>

              <div class="glass-card p-5">
                <h3 class="text-sm font-semibold text-white/60 mb-3">Per dag</h3>
                <div class="space-y-2">
                  <div
                    v-for="d in stats.global.matches_per_day"
                    :key="d.day"
                    class="flex items-center gap-3 text-sm"
                  >
                    <span class="w-24 text-white/60 shrink-0">{{ d.day }}</span>
                    <div class="flex-1 h-6 bg-white/5 rounded overflow-hidden">
                      <div
                        class="h-full bg-emerald-500/60 rounded"
                        :style="{ width: dayBarWidth(d.count) }"
                      ></div>
                    </div>
                    <span class="w-8 text-right text-white/40">{{ d.count }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useStats } from '../composables/useStats'
import StatItem from '../components/StatItem.vue'
import ColorBar from '../components/ColorBar.vue'

const router = useRouter()
const { stats, loading, error, fetchStats } = useStats()
const activeTab = ref<'Spelers' | 'Globaal'>('Spelers')
const expanded = ref(new Set<number>())

onMounted(fetchStats)

function togglePlayer(id: number) {
  if (expanded.value.has(id)) {
    expanded.value.delete(id)
  } else {
    expanded.value.add(id)
  }
}

function winrate(w: number, l: number): string {
  const total = w + l
  if (total === 0) return '-'
  return `${Math.round((w / total) * 100)}%`
}

function winrateColor(w: number, l: number): string {
  const total = w + l
  if (total === 0) return 'text-white/50'
  const pct = w / total
  if (pct >= 0.55) return 'text-emerald-400'
  if (pct <= 0.45) return 'text-red-400'
  return 'text-white/70'
}

function formatPct(v: number | null): string {
  return v !== null ? `${v}%` : '-'
}

function deltaText(delta: number | null): string {
  if (delta === null) return ''
  const sign = delta > 0 ? '+' : ''
  return `${sign}${delta}%`
}

const maxDayCount = computed(() => {
  if (!stats.value) return 1
  return Math.max(1, ...stats.value.global.matches_per_day.map(d => d.count))
})

function dayBarWidth(count: number): string {
  return `${(count / maxDayCount.value) * 100}%`
}
</script>

<style scoped>
.glass-card {
  background: rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  overflow: hidden;
}
.glass-btn {
  width: 44px;
  height: 44px;
  border-radius: 9999px;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.15s;
  background: rgba(255,255,255,0.12);
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  border: 1px solid rgba(255,255,255,0.2);
  box-shadow: 0 4px 24px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
}
.glass-btn:active {
  transform: scale(0.9);
}
</style>
