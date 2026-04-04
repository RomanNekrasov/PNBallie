<template>
  <div class="stats-shell">
    <div class="stats-grain"></div>

    <div class="max-w-[1060px] mx-auto px-4 sm:px-6 py-7 sm:py-9 relative z-10">
      <!-- Header -->
      <div class="flex items-center gap-3 mb-6">
        <button @click="router.push('/')" class="back-btn shrink-0" aria-label="Terug naar scorebord">
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 12H5" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
        </button>
        <div>
          <div class="club-eyebrow">PNBallie Clubhuis</div>
          <h1 class="text-3xl sm:text-4xl font-bold font-sport tracking-wide leading-none">Toernooibord</h1>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="club-panel text-center text-[var(--ink-soft)] py-12">
        Statistieken worden geladen...
      </div>

      <!-- Error -->
      <div v-else-if="error" class="club-panel text-center text-red-300 py-12">
        {{ error }}
      </div>

      <template v-else-if="stats">
        <!-- Top strip -->
        <div class="status-strip mb-6">
          <div class="status-item">
            <span class="status-label">Wedstrijden</span>
            <span class="status-value">{{ stats.global.total_matches }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Actieve kleurreeks</span>
            <span class="status-value">{{ activeColorStreak.label }} {{ activeColorStreak.value }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Rivaliteiten</span>
            <span class="status-value">{{ stats.head_to_head.matchups.length }}</span>
          </div>
        </div>

        <!-- Tabs -->
        <div class="tabs-track mb-7 overflow-x-auto no-scrollbar">
          <button
            v-for="tab in tabs"
            :key="tab"
            @click="activeTab = tab"
            class="tab-chip"
            :class="activeTab === tab ? 'tab-chip-active' : 'tab-chip-inactive'"
          >
            {{ tab }}
          </button>
        </div>

        <!-- Klassement -->
        <div v-if="activeTab === 'Klassement'" class="space-y-6">
          <div v-if="stats.leaderboard.length === 0" class="club-panel text-[var(--ink-soft)] text-center py-12">
            Nog geen wedstrijden gespeeld.
          </div>

          <template v-else>
            <div class="club-panel podium-wrap">
              <div class="podium-stage" :class="{ 'podium-stage-short': podiumEntries.length < 3 }">
                <article
                  v-for="entry in podiumEntries"
                  :key="entry.player_id"
                  class="podium-slot"
                  :class="podiumSlotClass(entry.rank)"
                >
                  <div class="podium-plate">
                    <div class="podium-name">{{ entry.name }}</div>
                    <div class="podium-elo">{{ entry.elo }} ELO</div>
                    <div class="podium-record">{{ entry.wins }}W · {{ entry.losses }}V</div>
                  </div>
                  <div class="podium-step">
                    <span class="podium-step-rank">{{ entry.rank }}</span>
                  </div>
                </article>
              </div>
            </div>

            <div v-if="ranglijstEntries.length > 0" class="club-panel overflow-hidden">
              <div class="leaderboard-grid board-head">
                <span>Pos.</span>
                <span>Speler</span>
                <span class="text-right">ELO</span>
                <span class="text-right">W / V</span>
                <span class="text-right">Win%</span>
              </div>
              <LeaderboardRow
                v-for="entry in ranglijstEntries"
                :key="entry.player_id"
                :rank="entry.rank"
                :name="entry.name"
                :elo="entry.elo"
                :wins="entry.wins"
                :losses="entry.losses"
                class="border-t border-[rgba(20,14,8,0.42)]"
              />
            </div>
          </template>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div class="space-y-4">
              <div class="club-panel p-5">
                <h3 class="section-header">Seizoensbalans</h3>
                <div class="text-3xl font-bold font-sport mb-4 tabular-nums">{{ stats.global.total_matches }} duels</div>
                <div class="space-y-3">
                  <ColorBar label="Alle duels" :orange="stats.global.orange_wins" :blue="stats.global.blue_wins" />
                  <ColorBar label="1 tegen 1" :orange="stats.global.orange_wins_1v1" :blue="stats.global.blue_wins_1v1" />
                  <ColorBar label="2 tegen 2" :orange="stats.global.orange_wins_2v2" :blue="stats.global.blue_wins_2v2" />
                </div>
              </div>

              <div class="club-panel p-5">
                <h3 class="section-header">Kleurreeksen</h3>
                <div class="grid grid-cols-2 gap-2">
                  <StatItem label="Oranje nu" :value="String(stats.global.current_orange_streak)" />
                  <StatItem label="Oranje record" :value="String(stats.global.longest_orange_streak)" />
                  <StatItem label="Blauw nu" :value="String(stats.global.current_blue_streak)" />
                  <StatItem label="Blauw record" :value="String(stats.global.longest_blue_streak)" />
                </div>
              </div>
            </div>

            <div class="space-y-4">
              <div class="club-panel p-5">
                <h3 class="section-header">Speelmomenten</h3>
                <div class="grid grid-cols-2 gap-2">
                  <StatItem
                    label="Lunch (voor 14:00)"
                    :value="`${stats.global.lunch_matches}`"
                    :sub="share(stats.global.lunch_matches, stats.global.total_matches)"
                  />
                  <StatItem
                    label="Middag (na 14:00)"
                    :value="`${stats.global.middag_matches}`"
                    :sub="share(stats.global.middag_matches, stats.global.total_matches)"
                  />
                </div>
              </div>

              <div class="club-panel p-5">
                <h3 class="section-header">Wedstrijden per dag</h3>
                <div class="space-y-2">
                  <div
                    v-for="d in stats.global.matches_per_day"
                    :key="d.day"
                    class="day-row"
                    :class="{ 'day-row-busiest': d.count === maxDayCount && d.count > 0 }"
                  >
                    <span class="day-name">{{ d.day }}</span>
                    <div class="day-track">
                      <div class="day-fill" :style="{ width: dayBarWidth(d.count) }"></div>
                    </div>
                    <span class="day-count">{{ d.count }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Spelers -->
        <div v-if="activeTab === 'Spelers'">
          <div v-if="stats.players.length === 0" class="club-panel text-[var(--ink-soft)] text-center py-12">
            Nog geen spelers.
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
            <article
              v-for="p in stats.players"
              :key="p.player_id"
              class="club-panel player-card"
            >
              <button @click="togglePlayer(p.player_id)" class="w-full flex items-start justify-between p-4 sm:p-5">
                <div class="min-w-0 flex-1 text-left">
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="text-lg font-bold font-sport tracking-wide truncate">{{ p.name }}</span>
                    <span class="elo-pill">{{ p.elo }} ELO</span>
                  </div>
                  <div class="player-subline">{{ p.wins }}W · {{ p.losses }}V · {{ p.wins + p.losses }} duels</div>
                  <div class="player-meter mt-3">
                    <div class="player-meter-fill" :style="{ width: winrateBarWidth(p.wins, p.losses) }"></div>
                  </div>
                </div>
                <div class="flex items-center gap-2 pl-3 shrink-0">
                  <span class="text-lg font-bold font-sport tabular-nums" :class="winrateColor(p.wins, p.losses)">
                    {{ winrate(p.wins, p.losses) }}
                  </span>
                  <svg
                    xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
                    fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"
                    class="transition-transform text-[var(--ink-dim)]"
                    :class="expanded.has(p.player_id) ? 'rotate-180' : ''"
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </div>
              </button>

              <div v-if="expanded.has(p.player_id)" class="px-4 pb-4 sm:px-5 sm:pb-5 space-y-2 text-sm">
                <div class="grid grid-cols-2 gap-2">
                  <StatItem label="1 tegen 1" :value="`${p.wins_1v1}W / ${p.losses_1v1}V`" />
                  <StatItem label="2 tegen 2" :value="`${p.wins_2v2}W / ${p.losses_2v2}V`" />
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <StatItem label="Winstreeks" :value="`${p.current_winstreak} (max ${p.longest_winstreak})`" />
                  <StatItem label="Verliesreeks" :value="`${p.current_losestreak} (max ${p.longest_losestreak})`" />
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <StatItem label="Oranje" :value="formatPct(p.winrate_orange)" :sub="deltaText(p.color_delta)" />
                  <StatItem label="Blauw" :value="formatPct(p.winrate_blue)" />
                </div>
                <div class="grid grid-cols-2 gap-2">
                  <StatItem label="Voor" :value="formatPct(p.winrate_voor)" :sub="deltaText(p.position_delta)" />
                  <StatItem label="Achter" :value="formatPct(p.winrate_achter)" />
                </div>
                <StatItem label="Grootste zege" :value="biggestVictory(p.biggest_victory_margin)" />
              </div>
            </article>
          </div>
        </div>

        <!-- Onderling -->
        <div v-if="activeTab === 'Onderling'" class="space-y-4">
          <div class="club-panel p-5">
            <h3 class="section-header">Onderlinge Vergelijking</h3>
            <div class="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center">
              <select v-model="h2hPlayer1" class="felt-select flex-1">
                <option :value="null" disabled>Speler 1</option>
                <option
                  v-for="p in stats.players"
                  :key="p.player_id"
                  :value="p.player_id"
                  :disabled="p.player_id === h2hPlayer2"
                >
                  {{ p.name }}
                </option>
              </select>
              <span class="text-[var(--ink-dim)] text-center text-sm font-bold font-sport tracking-wider">tegen</span>
              <select v-model="h2hPlayer2" class="felt-select flex-1">
                <option :value="null" disabled>Speler 2</option>
                <option
                  v-for="p in stats.players"
                  :key="p.player_id"
                  :value="p.player_id"
                  :disabled="p.player_id === h2hPlayer1"
                >
                  {{ p.name }}
                </option>
              </select>
            </div>
          </div>

          <div v-if="selectedMatchup" class="club-panel match-result p-6 text-center">
            <div class="flex items-center justify-center gap-4 sm:gap-6">
              <div class="flex-1 text-right min-w-0">
                <div class="text-lg font-bold font-sport truncate">{{ selectedMatchup.player1_name }}</div>
              </div>
              <div class="flex items-baseline gap-2 sm:gap-3">
                <span class="text-4xl font-bold font-sport tabular-nums" :class="selectedMatchup.player1_wins > selectedMatchup.player2_wins ? 'text-[var(--wood-light)]' : 'text-[var(--ink-dim)]'">{{ selectedMatchup.player1_wins }}</span>
                <span class="text-[var(--ink-dim)] text-xl font-sport">-</span>
                <span class="text-4xl font-bold font-sport tabular-nums" :class="selectedMatchup.player2_wins > selectedMatchup.player1_wins ? 'text-[var(--wood-light)]' : 'text-[var(--ink-dim)]'">{{ selectedMatchup.player2_wins }}</span>
              </div>
              <div class="flex-1 text-left min-w-0">
                <div class="text-lg font-bold font-sport truncate">{{ selectedMatchup.player2_name }}</div>
              </div>
            </div>
            <div class="text-xs text-[var(--ink-dim)] mt-2">{{ selectedMatchup.total }} duels</div>
          </div>

          <div v-else-if="h2hPlayer1 && h2hPlayer2" class="club-panel text-center text-[var(--ink-soft)] py-8">
            Deze spelers hebben nog geen duel tegen elkaar gespeeld.
          </div>

          <div v-else class="club-panel text-center text-[var(--ink-soft)] py-8">
            Kies twee spelers om de onderlinge stand te zien.
          </div>

          <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div v-if="stats.head_to_head.matchups.length > 0" class="club-panel p-5">
              <h3 class="section-header">Meeste duels</h3>
              <div class="space-y-1.5">
                <button
                  v-for="m in stats.head_to_head.matchups.slice(0, 6)"
                  :key="`${m.player1_id}-${m.player2_id}`"
                  @click="selectMatchup(m.player1_id, m.player2_id)"
                  class="duel-row"
                >
                  <span class="truncate">{{ m.player1_name }} tegen {{ m.player2_name }}</span>
                  <span class="text-[var(--ink-dim)] tabular-nums font-sport">{{ m.player1_wins }}-{{ m.player2_wins }} ({{ m.total }})</span>
                </button>
              </div>
            </div>

            <div v-if="duoLeaders.length > 0" class="club-panel p-5">
              <h3 class="section-header">Sterkste duo's</h3>
              <div class="space-y-1.5">
                <div
                  v-for="d in duoLeaders"
                  :key="`${d.player1_id}-${d.player2_id}`"
                  class="duo-row"
                >
                  <div class="truncate">{{ d.player1_name }} & {{ d.player2_name }}</div>
                  <div class="text-right shrink-0">
                    <div class="font-bold font-sport tabular-nums text-[var(--wood-light)]">{{ formatPct(d.winrate) }}</div>
                    <div class="text-[11px] text-[var(--ink-dim)]">{{ d.wins }}/{{ d.total }} gewonnen</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Erelijst -->
        <div v-if="activeTab === 'Erelijst'">
          <div v-if="stats.records.length === 0" class="club-panel text-[var(--ink-soft)] text-center py-12">
            Nog niet genoeg wedstrijden voor onderscheidingen.
          </div>

          <div v-else class="space-y-3">
            <div class="club-panel p-4">
              <h3 class="section-header">Clubhuisonderscheidingen</h3>
              <p class="text-sm text-[var(--ink-soft)]">
                Een overzicht van de opvallendste prestaties op tafel.
              </p>
            </div>

            <article
              v-for="(r, i) in stats.records"
              :key="r.key"
              class="record-plaque club-panel flex items-center gap-4 p-4"
              :style="{ animationDelay: `${i * 70}ms` }"
            >
              <div class="plaque-rank">{{ i + 1 }}</div>
              <div class="record-emoji shrink-0 w-12 h-12 rounded-xl flex items-center justify-center text-2xl">
                {{ r.emoji }}
              </div>
              <div class="flex-1 min-w-0">
                <div class="font-bold text-sm font-sport tracking-wide">{{ r.label }}</div>
                <div class="text-xs text-[var(--ink-dim)]">{{ r.description }}</div>
              </div>
              <div class="text-right shrink-0">
                <div class="font-bold text-sm text-[var(--wood-light)]">{{ r.value }}</div>
                <div class="text-xs text-[var(--ink-dim)] font-sport">{{ r.detail }}</div>
              </div>
            </article>
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
import LeaderboardRow from '../components/LeaderboardRow.vue'

const router = useRouter()
const { stats, loading, error, fetchStats } = useStats()

const tabs = ['Klassement', 'Spelers', 'Onderling', 'Erelijst'] as const
type Tab = typeof tabs[number]
const activeTab = ref<Tab>('Klassement')
const expanded = ref(new Set<number>())
const h2hPlayer1 = ref<number | null>(null)
const h2hPlayer2 = ref<number | null>(null)

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

function winrateBarWidth(w: number, l: number): string {
  const total = w + l
  if (total === 0) return '8%'
  return `${Math.max(8, Math.round((w / total) * 100))}%`
}

function winrateColor(w: number, l: number): string {
  const total = w + l
  if (total === 0) return 'text-[var(--ink-dim)]'
  const pct = w / total
  if (pct >= 0.55) return 'text-[var(--wood-light)]'
  if (pct <= 0.45) return 'text-red-300'
  return 'text-[var(--ink-soft)]'
}

function formatPct(v: number | null): string {
  if (v === null) return '-'
  return `${v.toLocaleString('nl-NL', { minimumFractionDigits: Number.isInteger(v) ? 0 : 1, maximumFractionDigits: 1 })}%`
}

function deltaText(delta: number | null): string {
  if (delta === null) return ''
  const formatted = Math.abs(delta).toLocaleString('nl-NL', { minimumFractionDigits: Number.isInteger(delta) ? 0 : 1, maximumFractionDigits: 1 })
  const sign = delta > 0 ? '+' : delta < 0 ? '-' : ''
  return `${sign}${formatted} pp`
}

function share(part: number, total: number): string {
  if (total === 0) return '0%'
  return `${Math.round((part / total) * 100)}%`
}

function biggestVictory(margin: number): string {
  if (margin <= 0) return '-'
  return `10-${10 - margin}`
}

function podiumSlotClass(rank: number): string {
  if (rank === 1) return 'podium-slot-first'
  if (rank === 2) return 'podium-slot-second'
  if (rank === 3) return 'podium-slot-third'
  return ''
}

const maxDayCount = computed(() => {
  if (!stats.value) return 1
  return Math.max(1, ...stats.value.global.matches_per_day.map(d => d.count))
})

function dayBarWidth(count: number): string {
  return `${(count / maxDayCount.value) * 100}%`
}

const activeColorStreak = computed(() => {
  if (!stats.value) return { label: '-', value: 0 }
  const orange = stats.value.global.current_orange_streak
  const blue = stats.value.global.current_blue_streak
  if (orange === 0 && blue === 0) return { label: 'Geen', value: 0 }
  if (orange >= blue) return { label: 'Oranje', value: orange }
  return { label: 'Blauw', value: blue }
})

const podiumEntries = computed(() => {
  if (!stats.value) return []
  const top = stats.value.leaderboard.slice(0, 3)
  if (top.length < 3) return top
  return [top[1], top[0], top[2]].filter((entry): entry is NonNullable<typeof entry> => entry !== undefined)
})

const ranglijstEntries = computed(() => {
  if (!stats.value) return []
  return stats.value.leaderboard.slice(3)
})

const duoLeaders = computed(() => {
  if (!stats.value) return []
  const preferred = [...stats.value.head_to_head.duos]
    .filter(d => d.total >= 3)
    .sort((a, b) => b.winrate - a.winrate || b.total - a.total)
    .slice(0, 6)
  if (preferred.length > 0) return preferred
  return stats.value.head_to_head.duos.slice(0, 6)
})

const selectedMatchup = computed(() => {
  if (!stats.value || !h2hPlayer1.value || !h2hPlayer2.value) return null
  const p1 = Math.min(h2hPlayer1.value, h2hPlayer2.value)
  const p2 = Math.max(h2hPlayer1.value, h2hPlayer2.value)
  const matchup = stats.value.head_to_head.matchups.find(
    m => m.player1_id === p1 && m.player2_id === p2
  )
  if (!matchup) return null
  if (h2hPlayer1.value === p1) return matchup
  return {
    ...matchup,
    player1_id: matchup.player2_id,
    player1_name: matchup.player2_name,
    player1_wins: matchup.player2_wins,
    player2_id: matchup.player1_id,
    player2_name: matchup.player1_name,
    player2_wins: matchup.player1_wins,
  }
})

function selectMatchup(p1: number, p2: number) {
  h2hPlayer1.value = p1
  h2hPlayer2.value = p2
}
</script>

<style scoped>
.stats-shell {
  --ink: #f3e7d1;
  --ink-soft: rgba(243, 231, 209, 0.72);
  --ink-dim: rgba(243, 231, 209, 0.45);
  --wood-light: #d4a853;
  --wood-mid: #8b5a2b;
  --orange: #e87d2f;
  --blue: #2d5fa1;
  position: relative;
  min-height: 100dvh;
  color: var(--ink);
  background:
    radial-gradient(1200px 640px at 0% -10%, rgba(212, 168, 83, 0.26), transparent 60%),
    radial-gradient(900px 520px at 100% 0%, rgba(45, 95, 161, 0.2), transparent 62%),
    linear-gradient(180deg, #1a1208 0%, #0f0a05 100%);
  overflow: hidden;
}

.stats-grain {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.2;
  background-image:
    repeating-linear-gradient(45deg, rgba(255, 255, 255, 0.03) 0 1px, transparent 1px 6px),
    radial-gradient(circle at 20% 15%, rgba(255, 255, 255, 0.07), transparent 30%),
    radial-gradient(circle at 80% 70%, rgba(255, 255, 255, 0.04), transparent 30%);
}

.club-eyebrow {
  font-size: 10px;
  line-height: 1.2;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgba(212, 168, 83, 0.82);
  margin-bottom: 6px;
}

.club-panel {
  background: linear-gradient(160deg, rgba(47, 107, 52, 0.62), rgba(26, 56, 30, 0.74));
  border: 1px solid rgba(160, 122, 73, 0.46);
  border-radius: 16px;
  box-shadow:
    0 14px 28px rgba(0, 0, 0, 0.3),
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    inset 0 -1px 0 rgba(0, 0, 0, 0.2);
}

.section-header {
  font-family: 'Barlow Condensed', system-ui, sans-serif;
  font-size: 11px;
  font-weight: 700;
  color: var(--wood-light);
  text-transform: uppercase;
  letter-spacing: 0.14em;
  margin-bottom: 12px;
}

.back-btn {
  width: 44px;
  height: 44px;
  border-radius: 9999px;
  color: var(--ink);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.15s, background-color 0.15s;
  background: rgba(139, 90, 43, 0.35);
  border: 1px solid rgba(180, 132, 81, 0.46);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.26), inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.back-btn:hover {
  background: rgba(139, 90, 43, 0.44);
}

.back-btn:active {
  transform: scale(0.92);
}

.status-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.status-item {
  background: rgba(0, 0, 0, 0.2);
  border: 1px solid rgba(160, 122, 73, 0.42);
  border-radius: 12px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.status-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--ink-dim);
}

.status-value {
  font-family: 'Barlow Condensed', system-ui, sans-serif;
  font-size: 20px;
  line-height: 1;
  color: var(--ink);
}

.tabs-track {
  display: flex;
  gap: 8px;
}

.tab-chip {
  white-space: nowrap;
  border-radius: 9999px;
  padding: 10px 16px;
  font-family: 'Barlow Condensed', system-ui, sans-serif;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.05em;
  border: 1px solid transparent;
  transition: 0.2s ease;
}

.tab-chip-active {
  color: var(--wood-light);
  background: rgba(139, 90, 43, 0.45);
  border-color: rgba(180, 132, 81, 0.55);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.tab-chip-inactive {
  color: var(--ink-soft);
  background: rgba(139, 90, 43, 0.18);
}

.tab-chip-inactive:hover {
  background: rgba(139, 90, 43, 0.28);
}

.podium-wrap {
  padding: 16px 14px 0;
  overflow: hidden;
}

.podium-stage {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  align-items: end;
}

.podium-stage-short {
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.podium-slot {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.podium-plate {
  border-radius: 12px;
  border: 1px solid rgba(171, 133, 84, 0.5);
  padding: 12px 10px;
  margin-bottom: 8px;
  background:
    linear-gradient(180deg, rgba(0, 0, 0, 0.24) 0%, rgba(0, 0, 0, 0.36) 100%),
    linear-gradient(145deg, rgba(61, 112, 66, 0.56), rgba(27, 58, 32, 0.66));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.podium-name {
  font-family: 'Barlow Condensed', system-ui, sans-serif;
  font-size: clamp(20px, 2.8vw, 26px);
  font-weight: 700;
  line-height: 1;
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.podium-elo {
  color: var(--wood-light);
  font-weight: 600;
  font-size: 12px;
  letter-spacing: 0.08em;
  margin-bottom: 4px;
}

.podium-record {
  color: var(--ink-soft);
  font-size: 12px;
}

.podium-step {
  height: 82px;
  border-radius: 12px 12px 0 0;
  border: 1px solid rgba(95, 62, 30, 0.7);
  border-bottom: none;
  background:
    linear-gradient(180deg, rgba(176, 121, 62, 0.6) 0%, rgba(113, 73, 34, 0.92) 100%),
    repeating-linear-gradient(
      -45deg,
      rgba(255, 255, 255, 0.05) 0 8px,
      rgba(0, 0, 0, 0.08) 8px 16px
    );
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.22),
    0 8px 16px rgba(0, 0, 0, 0.18);
  display: flex;
  align-items: center;
  justify-content: center;
}

.podium-step-rank {
  font-family: 'Barlow Condensed', system-ui, sans-serif;
  font-size: 42px;
  line-height: 1;
  font-weight: 700;
  color: rgba(255, 239, 214, 0.88);
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
}

.podium-slot-first .podium-plate {
  border-color: rgba(244, 203, 103, 0.78);
  background:
    linear-gradient(180deg, rgba(43, 31, 8, 0.58) 0%, rgba(27, 18, 6, 0.72) 100%),
    linear-gradient(145deg, rgba(198, 146, 48, 0.42), rgba(119, 80, 18, 0.44));
}

.podium-slot-first .podium-rank,
.podium-slot-first .podium-elo {
  color: #f4d89b;
}

.podium-slot-first .podium-step {
  height: 122px;
  border-color: rgba(170, 125, 35, 0.84);
  background:
    linear-gradient(180deg, rgba(244, 203, 103, 0.86) 0%, rgba(179, 122, 32, 0.95) 100%),
    repeating-linear-gradient(
      -45deg,
      rgba(255, 255, 255, 0.18) 0 7px,
      rgba(0, 0, 0, 0.12) 7px 14px
    );
}

.podium-slot-first .podium-step-rank {
  font-size: 58px;
  color: #fff1cf;
}

.podium-slot-second .podium-step {
  height: 96px;
  border-color: rgba(150, 156, 165, 0.86);
  background:
    linear-gradient(180deg, rgba(226, 230, 238, 0.82) 0%, rgba(132, 141, 154, 0.95) 100%),
    repeating-linear-gradient(
      -45deg,
      rgba(255, 255, 255, 0.16) 0 7px,
      rgba(0, 0, 0, 0.12) 7px 14px
    );
}

.podium-slot-third .podium-step {
  height: 76px;
  border-color: rgba(138, 90, 47, 0.88);
  background:
    linear-gradient(180deg, rgba(199, 133, 79, 0.84) 0%, rgba(126, 76, 35, 0.95) 100%),
    repeating-linear-gradient(
      -45deg,
      rgba(255, 255, 255, 0.12) 0 7px,
      rgba(0, 0, 0, 0.12) 7px 14px
    );
}

.podium-slot-second .podium-plate {
  border-color: rgba(206, 214, 225, 0.74);
  background:
    linear-gradient(180deg, rgba(35, 39, 46, 0.6) 0%, rgba(25, 30, 38, 0.7) 100%),
    linear-gradient(145deg, rgba(173, 181, 194, 0.35), rgba(92, 101, 115, 0.38));
}

.podium-slot-second .podium-rank,
.podium-slot-second .podium-elo {
  color: #d7dde7;
}

.podium-slot-second .podium-step-rank {
  color: #eef1f7;
}

.podium-slot-third .podium-plate {
  border-color: rgba(191, 131, 85, 0.72);
  background:
    linear-gradient(180deg, rgba(46, 30, 18, 0.6) 0%, rgba(31, 20, 12, 0.72) 100%),
    linear-gradient(145deg, rgba(161, 108, 65, 0.36), rgba(98, 58, 33, 0.42));
}

.podium-slot-third .podium-rank,
.podium-slot-third .podium-elo {
  color: #dfb57d;
}

.podium-slot-third .podium-step-rank {
  color: #f0d3b2;
}

.podium-stage-short .podium-slot .podium-step {
  height: 72px;
}

.leaderboard-grid {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr) 72px 94px 64px;
  gap: 8px;
  align-items: center;
}

.board-head {
  padding: 11px 16px;
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ink-dim);
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.22) 0%, rgba(0, 0, 0, 0.08) 100%);
}

.day-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.day-row-busiest .day-name,
.day-row-busiest .day-count {
  color: var(--wood-light);
}

.day-name {
  width: 86px;
  color: var(--ink-soft);
  flex-shrink: 0;
}

.day-track {
  flex: 1;
  height: 20px;
  border-radius: 9999px;
  background: rgba(0, 0, 0, 0.26);
  overflow: hidden;
}

.day-fill {
  height: 100%;
  min-width: 6%;
  border-radius: 9999px;
  background: linear-gradient(90deg, rgba(232, 125, 47, 0.9), rgba(212, 168, 83, 0.9));
}

.day-count {
  width: 28px;
  text-align: right;
  color: var(--ink-dim);
  font-variant-numeric: tabular-nums;
}

.player-card {
  overflow: hidden;
}

.player-subline {
  margin-top: 4px;
  font-size: 12px;
  color: var(--ink-dim);
}

.elo-pill {
  border-radius: 9999px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
  color: var(--wood-light);
  border: 1px solid rgba(212, 168, 83, 0.32);
  background: rgba(0, 0, 0, 0.18);
}

.player-meter {
  width: 100%;
  height: 7px;
  border-radius: 9999px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.28);
}

.player-meter-fill {
  height: 100%;
  border-radius: 9999px;
  background: linear-gradient(90deg, rgba(232, 125, 47, 0.9), rgba(212, 168, 83, 0.85));
}

.felt-select {
  appearance: none;
  background: rgba(0, 0, 0, 0.24);
  border: 1px solid rgba(160, 122, 73, 0.48);
  border-radius: 10px;
  color: var(--ink);
  padding: 10px 14px;
  font-size: 14px;
  outline: none;
  cursor: pointer;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='rgba(212,168,83,0.7)' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 32px;
}

.felt-select:focus {
  border-color: rgba(212, 168, 83, 0.65);
}

.felt-select option {
  background: #171006;
  color: var(--ink);
}

.match-result {
  border-color: rgba(212, 168, 83, 0.55);
}

.duel-row {
  width: 100%;
  border-radius: 10px;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid rgba(160, 122, 73, 0.28);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  text-align: left;
  font-size: 14px;
  transition: background-color 0.2s;
}

.duel-row:hover {
  background: rgba(139, 90, 43, 0.25);
}

.duo-row {
  border-radius: 10px;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid rgba(160, 122, 73, 0.28);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 14px;
}

.plaque-rank {
  width: 26px;
  height: 26px;
  border-radius: 9999px;
  border: 1px solid rgba(212, 168, 83, 0.5);
  background: rgba(0, 0, 0, 0.2);
  color: var(--wood-light);
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.record-emoji {
  background: rgba(139, 90, 43, 0.3);
  border: 1px solid rgba(180, 132, 81, 0.44);
  transition: transform 0.2s ease;
}

.record-plaque {
  opacity: 0;
  animation: plaque-rise 0.4s ease-out forwards;
}

.record-plaque:hover .record-emoji {
  transform: scale(1.13);
}

@keyframes plaque-rise {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.no-scrollbar::-webkit-scrollbar {
  display: none;
}

@media (max-width: 880px) {
  .podium-wrap {
    padding: 14px 10px 0;
  }

  .podium-stage {
    gap: 8px;
  }

  .podium-step-rank {
    font-size: 34px;
  }

  .podium-slot-first .podium-step-rank {
    font-size: 44px;
  }

  .podium-slot-first .podium-step {
    height: 106px;
  }

  .podium-slot-second .podium-step {
    height: 86px;
  }

  .podium-slot-third .podium-step {
    height: 70px;
  }
}

@media (max-width: 640px) {
  .status-strip {
    grid-template-columns: 1fr;
  }

  .leaderboard-grid {
    grid-template-columns: 44px minmax(0, 1fr) 62px 78px 52px;
    gap: 6px;
  }

  .board-head {
    font-size: 10px;
    padding: 10px 12px;
  }

  .day-name {
    width: 76px;
  }

  .podium-name {
    font-size: 19px;
  }

  .podium-plate {
    padding: 10px 8px;
  }

  .podium-slot-first .podium-step {
    height: 96px;
  }

  .podium-slot-second .podium-step {
    height: 78px;
  }

  .podium-slot-third .podium-step {
    height: 64px;
  }
}
</style>
