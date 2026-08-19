<template>
  <main class="stats-shell">
    <div class="broadcast-glow broadcast-glow-orange"></div>
    <div class="broadcast-glow broadcast-glow-blue"></div>

    <div class="stats-container">
      <header class="page-header">
        <button @click="router.push('/')" class="back-button" aria-label="Terug naar scorebord">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.4">
            <path d="M19 12H5" />
            <path d="m12 19-7-7 7-7" />
          </svg>
        </button>
        <div>
          <p class="eyebrow">PNBALLIE · ALL-TIME</p>
          <h1>Clubstatistieken</h1>
        </div>
        <div v-if="stats" class="live-badge"><span></span>{{ stats.global.total_matches }} duels</div>
      </header>

      <section v-if="loading" class="state-panel">Statistieken worden geladen…</section>
      <section v-else-if="error" class="state-panel state-error">
        <p>{{ error }}</p>
        <button @click="fetchStats">Opnieuw proberen</button>
      </section>

      <template v-else-if="stats">
        <nav class="tab-bar" aria-label="Statistieksecties">
          <button
            v-for="tab in tabs"
            :key="tab"
            @click="activeTab = tab"
            :class="{ active: activeTab === tab }"
          >{{ tab }}</button>
        </nav>

        <!-- Overview -->
        <section v-if="activeTab === 'Overzicht'" class="tab-content overview-grid">
          <article v-if="leader" class="leader-card broadcast-panel">
            <div class="leader-kicker">Huidige nummer één</div>
            <div class="leader-main">
              <div class="rank-mark">#{{ leader.rank }}</div>
              <div class="leader-copy">
                <h2>{{ leader.name }}</h2>
                <div class="leader-rating">{{ formatElo(leader.elo_precise) }} <span>ELO</span></div>
              </div>
              <div class="leader-form">
                <span>Laatste 5</span>
                <FormDots :results="leader.recent_form" />
              </div>
            </div>
            <div class="leader-footer">
              <strong>{{ formatPct(leader.winrate) }}</strong> winst
              <span>{{ leader.wins }}W · {{ leader.losses }}V</span>
            </div>
          </article>

          <div class="metric-grid">
            <article class="metric-card broadcast-panel orange-edge">
              <span>Wedstrijden</span><strong>{{ stats.global.total_matches }}</strong><small>all-time</small>
            </article>
            <article class="metric-card broadcast-panel">
              <span>1 tegen 1</span><strong>{{ stats.global.total_1v1 }}</strong><small>{{ share(stats.global.total_1v1, stats.global.total_matches) }}</small>
            </article>
            <article class="metric-card broadcast-panel blue-edge">
              <span>2 tegen 2</span><strong>{{ stats.global.total_2v2 }}</strong><small>{{ share(stats.global.total_2v2, stats.global.total_matches) }}</small>
            </article>
            <article class="metric-card broadcast-panel">
              <span>Goals per duel</span><strong>{{ decimal(stats.global.average_goals_per_match) }}</strong><small>gemiddeld</small>
            </article>
          </div>

          <div class="overview-columns">
            <article class="broadcast-panel section-card">
              <div class="section-title"><span>Kleurverdeling</span><small>winnaars</small></div>
              <div class="color-score">
                <div class="color-team orange-text"><strong>{{ stats.global.orange_wins }}</strong><span>Oranje</span></div>
                <div class="color-versus">VS</div>
                <div class="color-team blue-text"><strong>{{ stats.global.blue_wins }}</strong><span>Blauw</span></div>
              </div>
              <div class="split-bar" aria-label="Verdeling gewonnen wedstrijden">
                <div class="orange-fill" :style="{ width: shareRaw(stats.global.orange_wins, stats.global.total_matches) }"></div>
                <div class="blue-fill" :style="{ width: shareRaw(stats.global.blue_wins, stats.global.total_matches) }"></div>
              </div>
              <div class="format-lines">
                <div><span>1v1</span><b class="orange-text">{{ stats.global.orange_wins_1v1 }}</b><i></i><b class="blue-text">{{ stats.global.blue_wins_1v1 }}</b></div>
                <div><span>2v2</span><b class="orange-text">{{ stats.global.orange_wins_2v2 }}</b><i></i><b class="blue-text">{{ stats.global.blue_wins_2v2 }}</b></div>
              </div>
            </article>

            <article class="broadcast-panel section-card">
              <div class="section-title"><span>Speelactiviteit</span><small>Europe/Amsterdam</small></div>
              <div class="activity-summary">
                <div><strong>{{ stats.global.lunch_matches }}</strong><span>voor 14:00</span></div>
                <div><strong>{{ stats.global.middag_matches }}</strong><span>na 14:00</span></div>
              </div>
              <div class="day-chart">
                <div v-for="day in stats.global.matches_per_day" :key="day.day" class="day-column">
                  <div class="day-track"><div :style="{ height: dayHeight(day.count) }"></div></div>
                  <b>{{ day.count }}</b><span>{{ shortDay(day.day) }}</span>
                </div>
              </div>
            </article>
          </div>

          <article class="broadcast-panel highlights-panel">
            <div class="section-title">
              <span>Clubhighlights</span>
              <small>{{ stats.records.length }} onderscheidingen</small>
            </div>
            <div v-if="stats.records.length" class="highlights-grid">
              <div v-for="record in visibleRecords" :key="record.key" class="highlight-card">
                <div class="highlight-icon">{{ record.emoji }}</div>
                <div><span>{{ record.label }}</span><strong>{{ record.value }}</strong><small>{{ record.detail }}</small></div>
              </div>
            </div>
            <p v-else class="empty-copy">Nog niet genoeg wedstrijden voor onderscheidingen.</p>
            <button v-if="stats.records.length > 4" class="more-button" @click="showAllRecords = !showAllRecords">
              {{ showAllRecords ? 'Minder tonen' : `Toon alle ${stats.records.length}` }}
            </button>
          </article>
        </section>

        <!-- Leaderboard -->
        <section v-if="activeTab === 'Ranglijst'" class="tab-content">
          <article class="broadcast-panel ranking-panel">
            <div class="section-intro">
              <div><p class="eyebrow">Gecombineerde ELO</p><h2>Ranglijst</h2></div>
              <p>1v1 en 2v2 · K-factor 32</p>
            </div>
            <div v-if="stats.leaderboard.length" class="ranking-list">
              <div class="ranking-head ranking-row">
                <span>Pos.</span><span>Speler</span><span>ELO</span><span>W / V</span><span>Win%</span><span>Vorm</span>
              </div>
              <div
                v-for="entry in stats.leaderboard"
                :key="entry.player_id"
                class="ranking-row"
                :class="{ 'top-three': entry.rank <= 3 }"
              >
                <div class="rank-number">{{ entry.rank }}</div>
                <div class="ranking-player">
                  <strong>{{ entry.name }}</strong>
                  <div class="mobile-form"><FormDots :results="entry.recent_form" /></div>
                </div>
                <div class="ranking-elo">{{ formatElo(entry.elo_precise) }}</div>
                <div class="ranking-record">{{ entry.wins }}W / {{ entry.losses }}V</div>
                <div class="ranking-rate">{{ formatPct(entry.winrate) }}</div>
                <div class="ranking-form"><FormDots :results="entry.recent_form" /></div>
              </div>
            </div>
            <p v-else class="empty-copy">Nog geen wedstrijden gespeeld.</p>
          </article>
        </section>

        <!-- Player detail -->
        <section v-if="activeTab === 'Spelers'" class="tab-content player-layout">
          <div class="player-picker" role="list" aria-label="Kies een speler">
            <button
              v-for="player in stats.players"
              :key="player.player_id"
              @click="selectedPlayerId = player.player_id"
              :class="{ active: selectedPlayerId === player.player_id }"
            >{{ player.name }}</button>
          </div>

          <template v-if="selectedPlayer">
            <article class="broadcast-panel player-hero">
              <div>
                <p class="eyebrow">SPELERSPROFIEL</p>
                <h2>{{ selectedPlayer.name }}</h2>
                <FormDots :results="selectedPlayer.recent_form" />
              </div>
              <div class="player-rank"><span>#{{ selectedPlayer.rank ?? '–' }}</span><strong>{{ formatElo(selectedPlayer.elo_precise) }}</strong><small>ELO</small></div>
            </article>

            <div class="metric-grid player-metrics">
              <article class="metric-card broadcast-panel"><span>Duels</span><strong>{{ selectedPlayer.matches }}</strong><small>{{ selectedPlayer.wins }}W · {{ selectedPlayer.losses }}V</small></article>
              <article class="metric-card broadcast-panel"><span>Winrate</span><strong>{{ formatPct(selectedPlayer.winrate) }}</strong><small>all-time</small></article>
              <article class="metric-card broadcast-panel"><span>Actieve reeks</span><strong>{{ activePlayerStreak.value }}</strong><small>{{ activePlayerStreak.label }}</small></article>
              <article class="metric-card broadcast-panel"><span>Grootste zege</span><strong>{{ selectedPlayer.biggest_victory_score ?? '–' }}</strong><small>{{ selectedPlayer.biggest_victory_margin ? `+${selectedPlayer.biggest_victory_margin}` : 'geen' }}</small></article>
            </div>

            <div class="player-columns">
              <article class="broadcast-panel section-card">
                <div class="section-title"><span>Doelbalans</span><small>per wedstrijd</small></div>
                <div class="goal-grid">
                  <div><span>Voor</span><strong>{{ decimal(selectedPlayer.average_goals_for) }}</strong></div>
                  <div><span>Tegen</span><strong>{{ decimal(selectedPlayer.average_goals_against) }}</strong></div>
                  <div :class="differenceClass(selectedPlayer.average_goal_difference)"><span>Verschil</span><strong>{{ signed(selectedPlayer.average_goal_difference) }}</strong></div>
                </div>
              </article>

              <article class="broadcast-panel section-card">
                <div class="section-title"><span>Spelvorm</span><small>resultaten</small></div>
                <div class="performance-split">
                  <div><span>1 tegen 1</span><strong>{{ selectedPlayer.wins_1v1 }}W · {{ selectedPlayer.losses_1v1 }}V</strong><small>{{ recordRate(selectedPlayer.wins_1v1, selectedPlayer.losses_1v1) }}</small></div>
                  <div><span>2 tegen 2</span><strong>{{ selectedPlayer.wins_2v2 }}W · {{ selectedPlayer.losses_2v2 }}V</strong><small>{{ recordRate(selectedPlayer.wins_2v2, selectedPlayer.losses_2v2) }}</small></div>
                </div>
              </article>

              <article class="broadcast-panel section-card">
                <div class="section-title"><span>Kleur</span><small>{{ colorConclusion }}</small></div>
                <div class="context-split">
                  <div class="orange-context"><span>Oranje</span><strong>{{ formatPct(selectedPlayer.winrate_orange) }}</strong><small>{{ selectedPlayer.matches_orange }} duels</small></div>
                  <div class="blue-context"><span>Blauw</span><strong>{{ formatPct(selectedPlayer.winrate_blue) }}</strong><small>{{ selectedPlayer.matches_blue }} duels</small></div>
                </div>
              </article>

              <article class="broadcast-panel section-card">
                <div class="section-title"><span>Positie</span><small>{{ positionConclusion }}</small></div>
                <div class="context-split">
                  <div><span>Voor</span><strong>{{ formatPct(selectedPlayer.winrate_voor) }}</strong><small>{{ selectedPlayer.matches_voor }} duels</small></div>
                  <div><span>Achter</span><strong>{{ formatPct(selectedPlayer.winrate_achter) }}</strong><small>{{ selectedPlayer.matches_achter }} duels</small></div>
                </div>
              </article>
            </div>

            <article class="broadcast-panel section-card streak-card">
              <div class="section-title"><span>Reeksen</span><small>all-time</small></div>
              <div><span>Winst nu</span><strong>{{ selectedPlayer.current_winstreak }}</strong></div>
              <div><span>Winstrecord</span><strong>{{ selectedPlayer.longest_winstreak }}</strong></div>
              <div><span>Verlies nu</span><strong>{{ selectedPlayer.current_losestreak }}</strong></div>
              <div><span>Verliesrecord</span><strong>{{ selectedPlayer.longest_losestreak }}</strong></div>
            </article>
          </template>
        </section>

        <!-- Head-to-head -->
        <section v-if="activeTab === 'Onderling'" class="tab-content matchup-layout">
          <article class="broadcast-panel matchup-picker">
            <div class="section-title"><span>Onderlinge vergelijking</span><small>kies twee spelers</small></div>
            <div class="selector-row">
              <select v-model="h2hPlayer1" aria-label="Eerste speler">
                <option :value="null" disabled>Speler 1</option>
                <option v-for="player in stats.players" :key="player.player_id" :value="player.player_id" :disabled="player.player_id === h2hPlayer2">{{ player.name }}</option>
              </select>
              <span>VS</span>
              <select v-model="h2hPlayer2" aria-label="Tweede speler">
                <option :value="null" disabled>Speler 2</option>
                <option v-for="player in stats.players" :key="player.player_id" :value="player.player_id" :disabled="player.player_id === h2hPlayer1">{{ player.name }}</option>
              </select>
            </div>
          </article>

          <template v-if="h2hPlayer1 && h2hPlayer2">
            <article class="versus-banner broadcast-panel">
              <strong>{{ playerName(h2hPlayer1) }}</strong><span>TEGEN</span><strong>{{ playerName(h2hPlayer2) }}</strong>
            </article>
            <div class="matchup-cards">
              <article class="broadcast-panel matchup-card">
                <div class="matchup-label"><span>1V1</span><small>rechtstreeks duel</small></div>
                <div v-if="selected1v1" class="matchup-score"><strong>{{ selected1v1.player1_wins }}</strong><span>–</span><strong>{{ selected1v1.player2_wins }}</strong></div>
                <div v-else class="no-matchup">Nog geen 1v1-duels</div>
                <small v-if="selected1v1">{{ selected1v1.total }} wedstrijden</small>
              </article>
              <article class="broadcast-panel matchup-card">
                <div class="matchup-label"><span>2V2</span><small>tegenover elkaar</small></div>
                <div v-if="selected2v2" class="matchup-score"><strong>{{ selected2v2.player1_wins }}</strong><span>–</span><strong>{{ selected2v2.player2_wins }}</strong></div>
                <div v-else class="no-matchup">Nog niet tegenover elkaar</div>
                <small v-if="selected2v2">{{ selected2v2.total }} wedstrijden</small>
              </article>
              <article class="broadcast-panel matchup-card duo-card">
                <div class="matchup-label"><span>SAMEN</span><small>als duo in 2v2</small></div>
                <div v-if="selectedDuo" class="duo-score"><strong>{{ formatPct(selectedDuo.winrate) }}</strong><span>{{ selectedDuo.wins }}/{{ selectedDuo.total }} gewonnen</span></div>
                <div v-else class="no-matchup">Nog niet samen gespeeld</div>
              </article>
            </div>
          </template>
          <p v-else class="broadcast-panel empty-copy select-prompt">Kies twee spelers voor hun 1v1-, 2v2- en duoresultaten.</p>

          <div class="matchup-lists">
            <article class="broadcast-panel section-card">
              <div class="section-title"><span>Meeste confrontaties</span><small>alle spelvormen</small></div>
              <button v-for="matchup in stats.head_to_head.matchups.slice(0, 5)" :key="`${matchup.player1_id}-${matchup.player2_id}`" class="list-row" @click="selectPair(matchup.player1_id, matchup.player2_id)">
                <span>{{ matchup.player1_name }} <i>vs</i> {{ matchup.player2_name }}</span><strong>{{ matchup.player1_wins }}–{{ matchup.player2_wins }}</strong>
              </button>
            </article>
            <article class="broadcast-panel section-card">
              <div class="section-title"><span>Sterkste duo's</span><small>min. 3 duels</small></div>
              <div v-for="duo in strongestDuos" :key="`${duo.player1_id}-${duo.player2_id}`" class="list-row static-row">
                <span>{{ duo.player1_name }} <i>&</i> {{ duo.player2_name }}</span><strong>{{ formatPct(duo.winrate) }}</strong>
              </div>
              <p v-if="!strongestDuos.length" class="empty-copy">Nog te weinig duowedstrijden.</p>
            </article>
          </div>
        </section>
      </template>
    </div>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import FormDots from '../components/FormDots.vue'
import { useStats } from '../composables/useStats'
import type { DuoStat, HeadToHeadMatchup } from '../types'

const router = useRouter()
const { stats, loading, error, fetchStats } = useStats()

const tabs = ['Overzicht', 'Ranglijst', 'Spelers', 'Onderling'] as const
type Tab = typeof tabs[number]

const activeTab = ref<Tab>('Overzicht')
const selectedPlayerId = ref<number | null>(null)
const h2hPlayer1 = ref<number | null>(null)
const h2hPlayer2 = ref<number | null>(null)
const showAllRecords = ref(false)

onMounted(fetchStats)

watch(stats, value => {
  if (!value) return
  selectedPlayerId.value ??= value.leaderboard[0]?.player_id ?? value.players[0]?.player_id ?? null
}, { immediate: true })

const leader = computed(() => stats.value?.leaderboard[0] ?? null)
const selectedPlayer = computed(() => stats.value?.players.find(player => player.player_id === selectedPlayerId.value) ?? null)
const visibleRecords = computed(() => showAllRecords.value ? stats.value?.records ?? [] : stats.value?.records.slice(0, 4) ?? [])
const maxDayCount = computed(() => Math.max(1, ...(stats.value?.global.matches_per_day.map(day => day.count) ?? [1])))
const strongestDuos = computed(() => (stats.value?.head_to_head.duos ?? [])
  .filter(duo => duo.total >= 3)
  .sort((a, b) => b.winrate - a.winrate || b.total - a.total)
  .slice(0, 5))

const activePlayerStreak = computed(() => {
  const player = selectedPlayer.value
  if (!player) return { value: 0, label: 'geen' }
  if (player.current_winstreak) return { value: player.current_winstreak, label: 'winst op rij' }
  if (player.current_losestreak) return { value: player.current_losestreak, label: 'verlies op rij' }
  return { value: 0, label: 'geen reeks' }
})

const colorConclusion = computed(() => splitConclusion(
  selectedPlayer.value?.color_delta ?? null,
  selectedPlayer.value?.matches_orange ?? 0,
  selectedPlayer.value?.matches_blue ?? 0,
  'Oranje', 'Blauw',
))

const positionConclusion = computed(() => splitConclusion(
  selectedPlayer.value?.position_delta ?? null,
  selectedPlayer.value?.matches_voor ?? 0,
  selectedPlayer.value?.matches_achter ?? 0,
  'Voor', 'Achter',
))

const selected1v1 = computed(() => orientedMatchup(stats.value?.head_to_head.matchups_1v1 ?? []))
const selected2v2 = computed(() => orientedMatchup(stats.value?.head_to_head.matchups_2v2 ?? []))
const selectedDuo = computed<DuoStat | null>(() => {
  if (!stats.value || !h2hPlayer1.value || !h2hPlayer2.value) return null
  const first = Math.min(h2hPlayer1.value, h2hPlayer2.value)
  const second = Math.max(h2hPlayer1.value, h2hPlayer2.value)
  return stats.value.head_to_head.duos.find(duo => duo.player1_id === first && duo.player2_id === second) ?? null
})

function orientedMatchup(matchups: HeadToHeadMatchup[]): HeadToHeadMatchup | null {
  if (!h2hPlayer1.value || !h2hPlayer2.value) return null
  const first = Math.min(h2hPlayer1.value, h2hPlayer2.value)
  const second = Math.max(h2hPlayer1.value, h2hPlayer2.value)
  const matchup = matchups.find(item => item.player1_id === first && item.player2_id === second)
  if (!matchup) return null
  if (matchup.player1_id === h2hPlayer1.value) return matchup
  return {
    ...matchup,
    player1_id: matchup.player2_id,
    player1_name: matchup.player2_name,
    player1_wins: matchup.player2_wins,
    player2_id: matchup.player1_id,
    player2_name: matchup.player1_name,
    player2_wins: matchup.player1_wins,
  }
}

function formatElo(value: number): string {
  return value.toLocaleString('nl-NL', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

function formatPct(value: number | null): string {
  if (value === null) return '–'
  return `${value.toLocaleString('nl-NL', { maximumFractionDigits: 1 })}%`
}

function decimal(value: number | null): string {
  if (value === null) return '–'
  return value.toLocaleString('nl-NL', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
}

function signed(value: number | null): string {
  if (value === null) return '–'
  return `${value > 0 ? '+' : ''}${decimal(value)}`
}

function share(part: number, total: number): string {
  return total ? `${Math.round(part / total * 100)}%` : '0%'
}

function shareRaw(part: number, total: number): string {
  return total ? `${part / total * 100}%` : '50%'
}

function dayHeight(count: number): string {
  return count ? `${Math.max(8, count / maxDayCount.value * 100)}%` : '3px'
}

function shortDay(day: string): string {
  return day.slice(0, 2).toUpperCase()
}

function recordRate(wins: number, losses: number): string {
  return formatPct(wins + losses ? Math.round(wins / (wins + losses) * 1000) / 10 : null)
}

function differenceClass(value: number | null): string {
  if (value === null || value === 0) return ''
  return value > 0 ? 'positive' : 'negative'
}

function splitConclusion(delta: number | null, firstCount: number, secondCount: number, first: string, second: string): string {
  if (delta === null || firstCount < 3 || secondCount < 3) return 'meer data nodig'
  if (delta === 0) return 'geen verschil'
  return `${delta > 0 ? first : second} +${decimal(Math.abs(delta))} pp`
}

function playerName(id: number): string {
  return stats.value?.players.find(player => player.player_id === id)?.name ?? '?'
}

function selectPair(first: number, second: number) {
  h2hPlayer1.value = first
  h2hPlayer2.value = second
}
</script>

<style scoped>
.stats-shell {
  --bg: #080b11;
  --panel: rgba(18, 23, 32, 0.9);
  --panel-soft: rgba(25, 32, 43, 0.76);
  --line: rgba(255, 255, 255, 0.1);
  --muted: rgba(234, 241, 251, 0.58);
  --orange: #ff7a2f;
  --blue: #3b8cff;
  --green: #58e899;
  min-height: 100dvh;
  overflow-x: hidden;
  position: relative;
  color: #f5f8fc;
  background:
    linear-gradient(rgba(255, 255, 255, 0.018) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.018) 1px, transparent 1px),
    radial-gradient(circle at 50% -10%, #192231 0%, var(--bg) 48%);
  background-size: 32px 32px, 32px 32px, auto;
}

.broadcast-glow { position: fixed; width: 420px; height: 420px; border-radius: 50%; filter: blur(90px); opacity: .12; pointer-events: none; }
.broadcast-glow-orange { background: var(--orange); left: -260px; top: 12%; }
.broadcast-glow-blue { background: var(--blue); right: -260px; top: 4%; }

.stats-container { position: relative; z-index: 1; width: min(1120px, 100%); margin: 0 auto; padding: 24px 18px 64px; }
.page-header { display: flex; align-items: center; gap: 13px; margin-bottom: 22px; }
.page-header h1, .section-intro h2, .player-hero h2 { font: 800 clamp(30px, 6vw, 44px)/.94 'Barlow Condensed', system-ui, sans-serif; letter-spacing: .01em; }
.eyebrow { margin: 0 0 5px; color: var(--orange); font: 800 10px/1 'Barlow Condensed', system-ui, sans-serif; letter-spacing: .18em; text-transform: uppercase; }
.back-button { width: 44px; height: 44px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 14px; border: 1px solid var(--line); background: rgba(255,255,255,.06); color: white; }
.back-button:active { transform: scale(.94); }
.live-badge { margin-left: auto; display: flex; align-items: center; gap: 7px; color: var(--muted); font-size: 12px; }
.live-badge span { width: 7px; height: 7px; border-radius: 50%; background: var(--green); box-shadow: 0 0 12px var(--green); }

.state-panel, .broadcast-panel { border: 1px solid var(--line); background: linear-gradient(145deg, rgba(28,35,47,.95), rgba(12,16,23,.96)); box-shadow: 0 18px 45px rgba(0,0,0,.22), inset 0 1px rgba(255,255,255,.035); }
.state-panel { border-radius: 18px; padding: 44px 20px; text-align: center; color: var(--muted); }
.state-error { color: #ff9ca4; }
.state-error button, .more-button { margin-top: 15px; border: 1px solid rgba(255,122,47,.4); background: rgba(255,122,47,.12); color: #ffad7d; border-radius: 10px; padding: 9px 14px; font-weight: 700; }

.tab-bar { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; padding: 5px; margin-bottom: 20px; border: 1px solid var(--line); border-radius: 15px; background: rgba(6,9,14,.72); position: sticky; top: 8px; z-index: 20; backdrop-filter: blur(14px); }
.tab-bar button { min-width: 0; padding: 10px 5px; border-radius: 10px; color: var(--muted); font: 800 14px/1 'Barlow Condensed', system-ui, sans-serif; letter-spacing: .02em; transition: .18s ease; }
.tab-bar button.active { color: white; background: linear-gradient(135deg, rgba(255,122,47,.85), rgba(213,67,30,.82)); box-shadow: 0 6px 18px rgba(255,122,47,.2); }
.tab-content { animation: enter .22s ease-out both; }

.overview-grid { display: grid; gap: 14px; }
.leader-card { border-radius: 22px; padding: 19px; overflow: hidden; position: relative; border-color: rgba(255,122,47,.3); }
.leader-card::after { content: ''; position: absolute; inset: auto -8% -80% 35%; height: 220px; background: radial-gradient(circle, rgba(255,122,47,.24), transparent 64%); pointer-events: none; }
.leader-kicker, .section-title span { color: var(--muted); text-transform: uppercase; font: 800 10px/1 'Barlow Condensed', system-ui, sans-serif; letter-spacing: .14em; }
.leader-main { display: grid; grid-template-columns: auto 1fr; align-items: center; gap: 14px; margin-top: 15px; }
.rank-mark { font: 900 50px/1 'Barlow Condensed', system-ui, sans-serif; color: var(--orange); text-shadow: 0 0 28px rgba(255,122,47,.25); }
.leader-copy h2 { font: 800 36px/.9 'Barlow Condensed', system-ui, sans-serif; }
.leader-rating { margin-top: 6px; font: 800 19px/1 'Barlow Condensed', system-ui, sans-serif; }
.leader-rating span { font-size: 10px; color: var(--muted); letter-spacing: .12em; }
.leader-form { grid-column: 1 / -1; display: flex; align-items: center; justify-content: space-between; padding-top: 14px; border-top: 1px solid var(--line); }
.leader-form > span { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .1em; }
.leader-footer { position: relative; z-index: 1; display: flex; align-items: baseline; gap: 5px; margin-top: 14px; color: var(--muted); font-size: 12px; }
.leader-footer strong { color: var(--green); font: 800 22px/1 'Barlow Condensed', system-ui, sans-serif; }
.leader-footer span { margin-left: auto; }

.metric-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.metric-card { min-width: 0; border-radius: 16px; padding: 14px; display: flex; flex-direction: column; overflow: hidden; position: relative; }
.metric-card::after { content: ''; position: absolute; width: 50px; height: 3px; left: 14px; top: 0; background: rgba(255,255,255,.28); }
.metric-card.orange-edge::after { background: var(--orange); box-shadow: 0 0 14px var(--orange); }
.metric-card.blue-edge::after { background: var(--blue); box-shadow: 0 0 14px var(--blue); }
.metric-card span { color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .08em; }
.metric-card strong { margin-top: 5px; font: 850 29px/1 'Barlow Condensed', system-ui, sans-serif; white-space: nowrap; }
.metric-card small { margin-top: 4px; color: var(--muted); font-size: 11px; }

.overview-columns, .player-columns, .matchup-lists { display: grid; gap: 14px; }
.section-card, .highlights-panel, .matchup-picker { border-radius: 18px; padding: 17px; }
.section-title { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; margin-bottom: 17px; }
.section-title span { color: #eef4fc; font-size: 12px; }
.section-title small { color: var(--muted); font-size: 10px; text-align: right; }
.color-score { display: grid; grid-template-columns: 1fr auto 1fr; gap: 12px; align-items: center; }
.color-team { display: flex; flex-direction: column; }
.color-team:last-child { text-align: right; }
.color-team strong { font: 900 40px/1 'Barlow Condensed', system-ui, sans-serif; }
.color-team span { margin-top: 4px; color: var(--muted); font-size: 11px; text-transform: uppercase; }
.color-versus { color: rgba(255,255,255,.22); font: 900 13px/1 'Barlow Condensed', system-ui, sans-serif; }
.orange-text { color: var(--orange); }
.blue-text { color: var(--blue); }
.split-bar { height: 8px; display: flex; overflow: hidden; margin: 15px 0; border-radius: 99px; background: rgba(255,255,255,.05); }
.orange-fill { background: linear-gradient(90deg, #ff6425, #ff9a4d); }
.blue-fill { background: linear-gradient(90deg, #5da0ff, #2675e8); }
.format-lines { display: grid; gap: 8px; }
.format-lines > div { display: grid; grid-template-columns: 34px auto 1fr auto; align-items: center; gap: 9px; color: var(--muted); font-size: 11px; }
.format-lines i { height: 1px; background: var(--line); }
.activity-summary { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
.activity-summary div { padding: 10px; border-radius: 12px; background: rgba(255,255,255,.04); display: flex; justify-content: space-between; align-items: baseline; }
.activity-summary strong { font: 800 24px/1 'Barlow Condensed', system-ui, sans-serif; }
.activity-summary span { color: var(--muted); font-size: 10px; }
.day-chart { height: 100px; display: grid; grid-template-columns: repeat(7, 1fr); align-items: end; gap: 5px; margin-top: 14px; }
.day-column { min-width: 0; display: grid; grid-template-rows: 64px 13px 12px; text-align: center; gap: 2px; color: var(--muted); font-size: 9px; }
.day-track { display: flex; align-items: end; justify-content: center; height: 64px; border-radius: 7px; background: rgba(255,255,255,.035); overflow: hidden; }
.day-track div { width: 100%; background: linear-gradient(180deg, var(--orange), #cc3f21); border-radius: 7px 7px 2px 2px; }
.day-column b { color: white; font-size: 10px; }

.highlights-grid { display: grid; gap: 8px; }
.highlight-card { display: flex; align-items: center; gap: 12px; min-width: 0; padding: 11px; border: 1px solid rgba(255,255,255,.07); border-radius: 13px; background: rgba(255,255,255,.035); }
.highlight-icon { width: 38px; height: 38px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 11px; font-size: 20px; background: linear-gradient(145deg, rgba(255,122,47,.18), rgba(59,140,255,.12)); }
.highlight-card > div:last-child { min-width: 0; display: grid; }
.highlight-card span { color: var(--muted); font-size: 9px; text-transform: uppercase; letter-spacing: .09em; }
.highlight-card strong { margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font: 750 16px/1.1 'Barlow Condensed', system-ui, sans-serif; }
.highlight-card small { margin-top: 3px; color: var(--orange); font-size: 10px; }
.more-button { display: block; margin: 13px auto 0; }

.ranking-panel { border-radius: 20px; overflow: hidden; }
.section-intro { padding: 19px; display: flex; justify-content: space-between; align-items: end; border-bottom: 1px solid var(--line); }
.section-intro h2 { font-size: 34px; }
.section-intro > p { color: var(--muted); font-size: 10px; }
.ranking-row { display: grid; grid-template-columns: 52px minmax(100px, 1fr) 80px 92px 65px 140px; gap: 8px; align-items: center; padding: 12px 16px; border-top: 1px solid rgba(255,255,255,.065); }
.ranking-head { border-top: 0; color: var(--muted); font-size: 9px; text-transform: uppercase; letter-spacing: .1em; }
.ranking-row.top-three { background: linear-gradient(90deg, rgba(255,122,47,.1), transparent 68%); }
.rank-number { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 10px; border: 1px solid var(--line); color: var(--muted); font: 900 16px/1 'Barlow Condensed', system-ui, sans-serif; }
.top-three .rank-number { color: #15100a; border-color: #ffc166; background: linear-gradient(145deg, #ffd37b, #e99431); }
.ranking-player strong { font: 750 18px/1 'Barlow Condensed', system-ui, sans-serif; }
.ranking-elo { color: #ffb777; font: 800 17px/1 'Barlow Condensed', system-ui, sans-serif; }
.ranking-record, .ranking-rate { color: var(--muted); font-size: 12px; }
.ranking-rate { color: white; font-weight: 700; }
.mobile-form { display: none; margin-top: 6px; }

.player-layout { display: grid; gap: 13px; }
.player-picker { display: flex; gap: 7px; overflow-x: auto; padding-bottom: 2px; scrollbar-width: none; }
.player-picker::-webkit-scrollbar { display: none; }
.player-picker button { flex: 0 0 auto; padding: 9px 14px; border: 1px solid var(--line); border-radius: 99px; background: rgba(255,255,255,.04); color: var(--muted); font: 750 14px/1 'Barlow Condensed', system-ui, sans-serif; }
.player-picker button.active { color: white; border-color: rgba(59,140,255,.65); background: rgba(59,140,255,.2); box-shadow: inset 0 0 18px rgba(59,140,255,.1); }
.player-hero { border-radius: 20px; padding: 19px; display: flex; justify-content: space-between; align-items: center; border-color: rgba(59,140,255,.25); }
.player-hero h2 { margin-bottom: 10px; }
.player-rank { text-align: right; display: grid; }
.player-rank span { color: var(--blue); font: 900 26px/1 'Barlow Condensed', system-ui, sans-serif; }
.player-rank strong { margin-top: 7px; font: 900 22px/1 'Barlow Condensed', system-ui, sans-serif; }
.player-rank small { color: var(--muted); font-size: 9px; letter-spacing: .12em; }
.goal-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.goal-grid div, .performance-split div, .context-split div { padding: 12px; border: 1px solid rgba(255,255,255,.07); border-radius: 12px; background: rgba(255,255,255,.035); display: grid; }
.goal-grid span, .performance-split span, .context-split span { color: var(--muted); font-size: 9px; text-transform: uppercase; letter-spacing: .08em; }
.goal-grid strong { margin-top: 6px; font: 850 24px/1 'Barlow Condensed', system-ui, sans-serif; }
.goal-grid .positive strong { color: var(--green); }
.goal-grid .negative strong { color: #ff6874; }
.performance-split, .context-split { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.performance-split strong, .context-split strong { margin-top: 7px; font: 750 17px/1 'Barlow Condensed', system-ui, sans-serif; }
.performance-split small, .context-split small { margin-top: 5px; color: var(--muted); font-size: 10px; }
.orange-context { border-color: rgba(255,122,47,.25) !important; }
.orange-context strong { color: var(--orange); }
.blue-context { border-color: rgba(59,140,255,.25) !important; }
.blue-context strong { color: var(--blue); }
.streak-card { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.streak-card .section-title { grid-column: 1 / -1; }
.streak-card > div:not(.section-title) { display: grid; text-align: center; padding: 8px; border-right: 1px solid var(--line); }
.streak-card > div:last-child { border-right: 0; }
.streak-card span { color: var(--muted); font-size: 9px; text-transform: uppercase; }
.streak-card strong { margin-top: 5px; font: 800 23px/1 'Barlow Condensed', system-ui, sans-serif; }

.matchup-layout { display: grid; gap: 13px; }
.selector-row { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 8px; }
.selector-row select { min-width: 0; appearance: none; border: 1px solid var(--line); border-radius: 12px; padding: 12px 10px; background: #111722; color: white; font-weight: 700; }
.selector-row > span { color: var(--orange); font: 900 13px/1 'Barlow Condensed', system-ui, sans-serif; }
.versus-banner { border-radius: 17px; padding: 15px; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 10px; text-align: center; }
.versus-banner strong { font: 800 22px/1 'Barlow Condensed', system-ui, sans-serif; overflow: hidden; text-overflow: ellipsis; }
.versus-banner span { color: var(--muted); font-size: 9px; }
.matchup-cards { display: grid; gap: 10px; }
.matchup-card { border-radius: 17px; padding: 15px; text-align: center; }
.matchup-label { display: flex; justify-content: space-between; }
.matchup-label span { color: var(--orange); font: 900 13px/1 'Barlow Condensed', system-ui, sans-serif; letter-spacing: .1em; }
.matchup-label small, .matchup-card > small { color: var(--muted); font-size: 9px; }
.matchup-score { margin: 14px 0 5px; display: flex; justify-content: center; align-items: center; gap: 17px; }
.matchup-score strong { font: 900 42px/1 'Barlow Condensed', system-ui, sans-serif; }
.matchup-score strong:first-child { color: var(--orange); }
.matchup-score strong:last-child { color: var(--blue); }
.matchup-score span { color: rgba(255,255,255,.25); }
.duo-score { margin-top: 17px; display: grid; }
.duo-score strong { color: var(--green); font: 900 38px/1 'Barlow Condensed', system-ui, sans-serif; }
.duo-score span { margin-top: 6px; color: var(--muted); font-size: 10px; }
.no-matchup { padding: 25px 0 18px; color: var(--muted); font-size: 12px; }
.select-prompt { border-radius: 16px; padding: 28px 16px; }
.list-row { width: 100%; display: flex; justify-content: space-between; gap: 12px; padding: 10px 0; border-top: 1px solid rgba(255,255,255,.07); color: white; text-align: left; }
.list-row:first-of-type { border-top: 0; }
.list-row span { min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font-size: 12px; }
.list-row i { color: var(--muted); font-style: normal; }
.list-row strong { flex: 0 0 auto; color: var(--orange); font: 800 15px/1 'Barlow Condensed', system-ui, sans-serif; }
.static-row { cursor: default; }
.empty-copy { color: var(--muted); text-align: center; font-size: 12px; }

@keyframes enter { from { opacity: 0; transform: translateY(7px); } to { opacity: 1; transform: none; } }

@media (min-width: 720px) {
  .stats-container { padding: 34px 28px 80px; }
  .leader-card { padding: 24px; }
  .leader-main { grid-template-columns: auto 1fr auto; }
  .leader-form { grid-column: auto; display: grid; justify-items: end; border: 0; padding: 0; gap: 8px; }
  .metric-grid { grid-template-columns: repeat(4, 1fr); }
  .overview-columns, .player-columns, .matchup-lists { grid-template-columns: repeat(2, 1fr); }
  .highlights-grid { grid-template-columns: repeat(2, 1fr); }
  .matchup-cards { grid-template-columns: repeat(3, 1fr); }
  .player-metrics { grid-template-columns: repeat(4, 1fr); }
  .tab-bar { position: static; width: fit-content; grid-template-columns: repeat(4, 130px); }
}

@media (max-width: 719px) {
  .stats-container { padding-left: 14px; padding-right: 14px; }
  .live-badge { display: none; }
  .tab-bar button { font-size: 12px; }
  .ranking-head { display: none; }
  .ranking-row { grid-template-columns: 36px minmax(0, 1fr) 62px 48px; padding: 12px; }
  .ranking-record, .ranking-form { display: none; }
  .mobile-form { display: block; }
  .ranking-rate { text-align: right; }
  .ranking-elo { font-size: 15px; }
  .streak-card { grid-template-columns: repeat(2, 1fr); }
  .streak-card > div:nth-of-type(2) { border-right: 0; }
  .streak-card > div:nth-of-type(3), .streak-card > div:nth-of-type(4) { border-top: 1px solid var(--line); }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; transition-duration: .01ms !important; }
}
</style>
