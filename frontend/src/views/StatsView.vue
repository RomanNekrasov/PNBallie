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
          <p class="eyebrow">PNBALLIE · {{ periodLabel }}</p>
          <h1>Clubstatistieken</h1>
        </div>
        <div class="page-header-actions"><div v-if="stats" class="live-badge"><span></span>{{ stats.global.total_matches }} duels</div><SettingsMenu /></div>
      </header>

      <div class="stats-filters" aria-label="Statistiekfilters">
        <label>Spelvorm
          <select v-model="mode" aria-label="Spelvorm">
            <option value="all">Alles samen</option>
            <option value="1v1">Alleen 1v1</option>
            <option value="2v2">Alleen 2v2</option>
          </select>
        </label>
        <label>Periode
          <select v-model="period" aria-label="Periode">
            <option value="all">All-time</option>
            <option value="30d">Laatste 30 dagen</option>
            <option value="50">Laatste 50 wedstrijden</option>
          </select>
        </label>
      </div>
      <p v-if="period === '30d'" class="filter-description">Vandaag en de vorige 29 dagen, volgens de Nederlandse kalender.</p>
      <p v-else-if="period === '50'" class="filter-description">De laatste 50 wedstrijden van de gekozen spelvorm.</p>

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
            <div class="leader-kicker">Nummer één in deze selectie</div>
            <div class="leader-main">
              <StatsPlayerAvatar :name="leader.name" :avatar-url="leader.avatar_url" :size="84" crowned />
              <div class="leader-copy">
                <h2><span class="rank-inline">#{{ leader.rank }}</span>{{ leader.name }}</h2>
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
              <span>Wedstrijden</span><strong>{{ stats.global.total_matches }}</strong><small>{{ periodLabel }}</small>
            </article>
            <article class="metric-card broadcast-panel">
              <span>1 tegen 1</span><strong>{{ stats.global.total_1v1 }}</strong><small>{{ share(stats.global.total_1v1, stats.global.total_matches) }}</small>
            </article>
            <article class="metric-card broadcast-panel blue-edge">
              <span>2 tegen 2</span><strong>{{ stats.global.total_2v2 }}</strong><small>{{ share(stats.global.total_2v2, stats.global.total_matches) }}</small>
            </article>
            <article class="metric-card broadcast-panel">
              <span>Doelverschil per duel</span><strong>{{ decimal(stats.global.average_goal_difference) }}</strong><small>gemiddelde winstmarge</small>
            </article>
          </div>

          <div class="overview-columns">
            <article class="broadcast-panel section-card">
              <div class="section-title"><span>Wins per kleur</span><small>gewonnen wedstrijden</small></div>
              <div class="format-lines">
                <ColorBar label="Totaal" :orange="stats.global.orange_wins" :blue="stats.global.blue_wins" />
                <ColorBar v-if="mode !== '2v2'" label="1v1" :orange="stats.global.orange_wins_1v1" :blue="stats.global.blue_wins_1v1" />
                <ColorBar v-if="mode !== '1v1'" label="2v2" :orange="stats.global.orange_wins_2v2" :blue="stats.global.blue_wins_2v2" />
              </div>
            </article>

            <article class="broadcast-panel section-card">
              <div class="section-title"><span>Speelactiviteit</span><small>wedstrijden per dag</small></div>
              <div class="activity-summary">
                <div class="activity-before"><strong>{{ stats.global.lunch_matches }}</strong><span><i></i>voor 14:00</span></div>
                <div class="activity-after"><strong>{{ stats.global.middag_matches }}</strong><span><i></i>vanaf 14:00</span></div>
              </div>
              <div class="day-chart">
                <div v-for="day in stats.global.matches_per_day" :key="day.day" class="day-column">
                  <div class="day-track" :aria-label="`${day.day}: ${day.before_14} voor 14:00, ${day.from_14} vanaf 14:00`" :title="`${day.before_14} voor 14:00 · ${day.from_14} vanaf 14:00`">
                    <div class="activity-stack" :style="{ height: dayHeight(day.count) }">
                      <div class="activity-after-fill" :style="{ flex: day.from_14 }"></div>
                      <div class="activity-before-fill" :style="{ flex: day.before_14 }"></div>
                    </div>
                  </div>
                  <b>{{ day.count }}</b><span>{{ shortDay(day.day) }}</span>
                </div>
              </div>
            </article>
          </div>

          <article class="broadcast-panel recent-panel">
            <div class="section-title">
              <span>Recente uitslagen</span>
              <small>laatste {{ recentMatches.length }}</small>
            </div>
            <div v-if="recentMatches.length" class="recent-match-list">
              <article v-for="match in recentMatches" :key="match.id" class="recent-match">
                <div class="recent-match-head">
                  <time :datetime="match.played_at">{{ formatMatchTime(match.played_at) }}</time>
                  <span>{{ match.players.length === 2 ? '1 tegen 1' : '2 tegen 2' }}</span>
                </div>
                <div class="recent-teams">
                  <div class="recent-team orange-team">
                    <div v-for="player in matchPlayers(match, 'orange')" :key="player.id" class="recent-player">
                      <StatsPlayerAvatar :name="player.name" :avatar-url="player.avatarUrl" :size="34" :crowned="isRankOne(player.id)" />
                      <div><strong>{{ player.name }}</strong><small>{{ positionLabel(player.position) }}</small></div>
                    </div>
                  </div>
                  <div class="recent-score" :aria-label="`Oranje ${match.orange_score}, Blauw ${match.blue_score}`">
                    <strong class="orange-text" :class="{ winner: match.orange_score > match.blue_score }">{{ match.orange_score }}</strong>
                    <span>–</span>
                    <strong class="blue-text" :class="{ winner: match.blue_score > match.orange_score }">{{ match.blue_score }}</strong>
                  </div>
                  <div class="recent-team blue-team">
                    <div v-for="player in matchPlayers(match, 'blue')" :key="player.id" class="recent-player">
                      <StatsPlayerAvatar :name="player.name" :avatar-url="player.avatarUrl" :size="34" :crowned="isRankOne(player.id)" />
                      <div><strong>{{ player.name }}</strong><small>{{ positionLabel(player.position) }}</small></div>
                    </div>
                  </div>
                </div>
              </article>
            </div>
            <p v-else class="empty-copy">Nog geen uitslagen.</p>
          </article>

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
              <div><p class="eyebrow">{{ modeLabel }} · ELO</p><h2>Ranglijst</h2></div>
              <p>Vanaf 1000 binnen deze selectie</p>
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
                  <StatsPlayerAvatar :name="entry.name" :avatar-url="entry.avatar_url" :size="42" :crowned="entry.rank === 1" />
                  <div>
                    <strong>{{ entry.name }}</strong>
                    <div class="mobile-form"><FormDots :results="entry.recent_form" /></div>
                  </div>
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
            >
              <StatsPlayerAvatar :name="player.name" :avatar-url="player.avatar_url" :size="30" :crowned="player.rank === 1" />
              <span>{{ player.name }}</span>
            </button>
          </div>

          <template v-if="selectedPlayer">
            <article class="broadcast-panel player-hero">
              <StatsPlayerAvatar :name="selectedPlayer.name" :avatar-url="selectedPlayer.avatar_url" :size="72" :crowned="selectedPlayer.rank === 1" />
              <div class="player-hero-copy">
                <p class="eyebrow">SPELERSPROFIEL</p>
                <h2>{{ selectedPlayer.name }} <span v-if="selectedPlayer.current_winstreak >= 3" class="streak-flame" :aria-label="`${selectedPlayer.current_winstreak} overwinningen op rij`">🔥</span></h2>
                <FormDots :results="selectedPlayer.recent_form" />
              </div>
              <div class="player-rank"><span>#{{ selectedPlayer.rank ?? '–' }}</span><strong>{{ formatElo(selectedPlayer.elo_precise) }}</strong><small>ELO</small></div>
            </article>

            <div class="metric-grid player-metrics">
              <article class="metric-card broadcast-panel"><span>Duels</span><strong>{{ selectedPlayer.matches }}</strong><small>{{ selectedPlayer.wins }}W · {{ selectedPlayer.losses }}V</small></article>
              <article class="metric-card broadcast-panel"><span>Winrate</span><strong>{{ formatPct(selectedPlayer.winrate) }}</strong><small>{{ periodLabel }}</small></article>
              <article class="metric-card broadcast-panel"><span>Actieve reeks</span><strong>{{ activePlayerStreak.value }}</strong><small>{{ activePlayerStreak.label }}</small></article>
              <article class="metric-card broadcast-panel"><span>Grootste zege</span><strong>{{ selectedPlayer.biggest_victory_score ?? '–' }}</strong><small>{{ selectedPlayer.biggest_victory_margin ? `+${selectedPlayer.biggest_victory_margin}` : 'geen' }}</small></article>
            </div>

            <article class="broadcast-panel section-card">
              <div class="section-title"><span>Verdiende badges</span><small>blijven bij je profiel</small></div>
              <PlayerBadges :badges="selectedPlayer.badges" />
            </article>

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
              <div class="versus-player"><StatsPlayerAvatar :name="playerName(h2hPlayer1)" :avatar-url="playerAvatarUrl(h2hPlayer1)" :size="52" :crowned="isRankOne(h2hPlayer1)" /><strong>{{ playerName(h2hPlayer1) }}</strong></div>
              <span>TEGEN</span>
              <div class="versus-player"><StatsPlayerAvatar :name="playerName(h2hPlayer2)" :avatar-url="playerAvatarUrl(h2hPlayer2)" :size="52" :crowned="isRankOne(h2hPlayer2)" /><strong>{{ playerName(h2hPlayer2) }}</strong></div>
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
import SettingsMenu from '../components/SettingsMenu.vue'
import ColorBar from '../components/ColorBar.vue'
import PlayerBadges from '../components/PlayerBadges.vue'
import StatsPlayerAvatar from '../components/StatsPlayerAvatar.vue'
import { useStats } from '../composables/useStats'
import { currentGroup } from '../auth'
import { formatLocalDateTime } from '../dateTime'
import type { DuoStat, HeadToHeadMatchup, Match } from '../types'
import { trackEvent, trackScreen } from '../analytics'

const router = useRouter()
const { stats, loading, error, mode, period, fetchStats } = useStats()

const tabs = ['Overzicht', 'Ranglijst', 'Spelers', 'Onderling'] as const
type Tab = typeof tabs[number]

const activeTab = ref<Tab>('Overzicht')
watch(activeTab, tab => trackScreen(({ Overzicht: 'stats_overview', Ranglijst: 'stats_ranking', Spelers: 'stats_players', Onderling: 'stats_matchups' } as const)[tab]), { immediate: true })
const selectedPlayerId = ref<number | null>(null)
const h2hPlayer1 = ref<number | null>(null)
const h2hPlayer2 = ref<number | null>(null)
const showAllRecords = ref(false)
const recentMatches = computed(() => stats.value?.recent_matches ?? [])
const periodLabel = computed(() => ({ all: 'All-time', '30d': 'Laatste 30 dagen', '50': 'Laatste 50 wedstrijden' })[period.value])
const modeLabel = computed(() => mode.value === 'all' ? '1v1 en 2v2' : mode.value)

onMounted(fetchStats)
watch([mode, period], () => {
  trackEvent('stats_filters_changed', { mode: mode.value, period: period.value })
  void fetchStats()
})
watch([h2hPlayer1, h2hPlayer2], ([first, second]) => { if (first && second) trackEvent('comparison_selected') })

watch(stats, value => {
  if (!value) return
  if (!value.players.some(player => player.player_id === selectedPlayerId.value)) {
    selectedPlayerId.value = currentGroup.value?.player_id ?? value.leaderboard[0]?.player_id ?? value.players[0]?.player_id ?? null
  }
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

function dayHeight(count: number): string {
  return `${count / maxDayCount.value * 100}%`
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

function playerAvatarUrl(id: number): string | null {
  return stats.value?.players.find(player => player.player_id === id)?.avatar_url ?? null
}

function matchPlayers(match: Match, side: 'orange' | 'blue') {
  return match.players
    .filter(player => player.side === side)
    .map(player => ({
      id: player.player_id,
      name: playerName(player.player_id),
      avatarUrl: playerAvatarUrl(player.player_id),
      position: player.position,
    }))
}

function positionLabel(position: 'voor' | 'achter' | 'solo'): string {
  if (position === 'solo') return 'Solo'
  return position === 'voor' ? 'Voor' : 'Achter'
}

function formatMatchTime(value: string): string {
  return formatLocalDateTime(value)
}

function isRankOne(id: number): boolean {
  return stats.value?.leaderboard.some(player => player.player_id === id && player.rank === 1) ?? false
}

function selectPair(first: number, second: number) {
  h2hPlayer1.value = first
  h2hPlayer2.value = second
}
</script>

<style scoped>
.stats-shell {
  --bg: #080b11;
  --panel: #171f2b;
  --panel-soft: #202a38;
  --line: #303b4b;
  --muted: #96a3b5;
  --orange: #ff7a2f;
  --blue: #3b8cff;
  --green: #58e899;
  min-height: 100dvh;
  overflow-x: hidden;
  position: relative;
  color: #f5f8fc;
  background: #0b1018;
}

.broadcast-glow { display: none; }
.broadcast-glow-orange { background: var(--orange); left: -260px; top: 12%; }
.broadcast-glow-blue { background: var(--blue); right: -260px; top: 4%; }

.stats-container { position: relative; z-index: 1; width: min(1120px, 100%); margin: 0 auto; padding: 24px 18px 64px; }
.page-header { display: flex; align-items: center; gap: 13px; margin-bottom: 22px; }
.page-header h1, .section-intro h2, .player-hero h2 { font: 800 clamp(30px, 6vw, 44px)/.94 'Barlow Condensed', system-ui, sans-serif; letter-spacing: .01em; }
.eyebrow { margin: 0 0 5px; color: var(--orange); font: 800 10px/1 'Barlow Condensed', system-ui, sans-serif; letter-spacing: .18em; text-transform: uppercase; }
.back-button { width: 44px; height: 44px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 14px; border: 1px solid var(--line); background: #202a38; color: white; }
.back-button:active { transform: scale(.94); }
.page-header-actions { margin-left: auto; display: flex; align-items: center; gap: 15px; flex: 0 0 auto; }
.live-badge { display: flex; align-items: center; gap: 7px; color: var(--muted); font-size: 12px; }
.live-badge span { width: 7px; height: 7px; border-radius: 50%; background: var(--green); box-shadow: 0 0 12px var(--green); }

.state-panel, .broadcast-panel { border: 1px solid var(--line); background: var(--panel); box-shadow: 0 12px 28px #05070b; }
.state-panel { border-radius: 18px; padding: 44px 20px; text-align: center; color: var(--muted); }
.state-error { color: #ff9ca4; }
.state-error button, .more-button { margin-top: 15px; border: 1px solid #a94923; background: #512716; color: #ffc19d; border-radius: 10px; padding: 9px 14px; font-weight: 700; }

.tab-bar { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 6px; padding: 5px; margin-bottom: 20px; border: 1px solid var(--line); border-radius: 15px; background: #101722; position: sticky; top: 8px; z-index: 20; }
.tab-bar button { min-width: 0; padding: 10px 5px; border-radius: 10px; color: var(--muted); font: 800 14px/1 'Barlow Condensed', system-ui, sans-serif; letter-spacing: .02em; transition: .18s ease; }
.tab-bar button.active { color: white; background: #d95b26; box-shadow: 0 5px 12px #070a0f; }
.tab-bar button:hover, .player-picker button:hover { color: white; background: #34435a; }
.tab-bar button.active:hover { background: #ed7038; }
.stats-shell button:focus-visible, .stats-shell select:focus-visible { outline: 2px solid #ffbd8c; outline-offset: 3px; }
.stats-filters { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 15px; }
.stats-filters label { flex: 1 1 140px; display: grid; gap: 6px; color: var(--muted); font-size: 11px; }
.stats-filters select { width: 100%; min-height: 44px; padding: 9px 12px; border: 1px solid var(--line); border-radius: 11px; background: var(--panel-soft); color: white; font-size: 13px; }
.filter-description { margin: -5px 0 15px; color: var(--muted); font-size: 11px; }
.streak-flame { font-size: .6em; vertical-align: middle; }
.tab-content { animation: enter .22s ease-out both; }

.overview-grid { display: grid; gap: 14px; }
.leader-card { border-radius: 22px; padding: 19px; overflow: hidden; position: relative; border-color: #77401f; background: #211d1d; }
.leader-kicker, .section-title span { color: var(--muted); text-transform: uppercase; font: 800 10px/1 'Barlow Condensed', system-ui, sans-serif; letter-spacing: .14em; }
.leader-main { display: grid; grid-template-columns: auto 1fr; align-items: center; gap: 14px; margin-top: 19px; }
.rank-inline { margin-right: 8px; color: var(--orange); }
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
.activity-summary { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
.activity-summary div { padding: 10px; border-radius: 12px; background: var(--panel-soft); display: flex; justify-content: space-between; align-items: baseline; }
.activity-summary strong { font: 800 24px/1 'Barlow Condensed', system-ui, sans-serif; }
.activity-summary span { color: var(--muted); font-size: 10px; }
.activity-summary span i { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 4px; }
.activity-before strong { color: #ffb078; }
.activity-after strong { color: #86b5ff; }
.activity-before span i, .activity-before-fill { background: var(--orange); }
.activity-after span i, .activity-after-fill { background: var(--blue); }
.day-chart { height: 100px; display: grid; grid-template-columns: repeat(7, 1fr); align-items: end; gap: 5px; margin-top: 14px; }
.day-column { min-width: 0; display: grid; grid-template-rows: 64px 13px 12px; text-align: center; gap: 2px; color: var(--muted); font-size: 9px; }
.day-track { display: flex; align-items: end; justify-content: center; height: 64px; border-radius: 7px; background: #101722; overflow: hidden; }
.activity-stack { width: 100%; display: flex; flex-direction: column; overflow: hidden; border-radius: 7px 7px 2px 2px; }
.day-column b { color: white; font-size: 10px; }

.recent-panel { border-radius: 18px; padding: 17px; }
.recent-match-list { display: grid; gap: 9px; }
.recent-match { display: grid; gap: 10px; padding: 13px; border: 1px solid var(--line); border-radius: 14px; background: var(--panel-soft); }
.recent-match-head { min-width: 0; display: flex; align-items: center; gap: 7px; color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: .05em; }
.recent-match-head time { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.recent-match-head span { flex: 0 0 auto; padding: 3px 6px; border-radius: 6px; color: #cad4e2; background: #111822; }
.recent-score { display: flex; align-items: center; gap: 4px; align-self: center; }
.recent-score strong { min-width: 20px; text-align: center; font: 900 25px/1 'Barlow Condensed', system-ui, sans-serif; opacity: .72; }
.recent-score strong.winner { opacity: 1; }
.recent-score span { color: #596578; }
.recent-teams { min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); gap: 6px; }
.recent-team { min-width: 0; display: grid; gap: 5px; padding: 7px; border-radius: 10px; }
.orange-team { border-left: 3px solid var(--orange); background: #302016; }
.blue-team { border-right: 3px solid var(--blue); background: #172741; }
.blue-team .recent-player { flex-direction: row-reverse; text-align: right; }
.recent-player { min-width: 0; display: flex; align-items: center; gap: 6px; }
.recent-player > div { min-width: 0; display: grid; }
.recent-player strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font: 750 14px/1 'Barlow Condensed', system-ui, sans-serif; }
.recent-player small { margin-top: 3px; color: var(--muted); font-size: 9px; text-transform: uppercase; letter-spacing: .09em; }

.highlights-grid { display: grid; gap: 8px; }
.highlight-card { display: flex; align-items: center; gap: 12px; min-width: 0; padding: 11px; border: 1px solid var(--line); border-radius: 13px; background: var(--panel-soft); }
.highlight-icon { width: 38px; height: 38px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 11px; font-size: 20px; background: #30394a; }
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
.ranking-row.top-three { background: #211d1d; }
.rank-number { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 10px; border: 1px solid var(--line); color: var(--muted); font: 900 16px/1 'Barlow Condensed', system-ui, sans-serif; }
.top-three .rank-number { color: #15100a; border-color: #ffc166; background: linear-gradient(145deg, #ffd37b, #e99431); }
.ranking-player { min-width: 0; display: flex; align-items: center; gap: 10px; }
.ranking-player > div { min-width: 0; }
.ranking-player strong { display: block; overflow: hidden; text-overflow: ellipsis; font: 750 18px/1 'Barlow Condensed', system-ui, sans-serif; }
.ranking-elo { color: #ffb777; font: 800 17px/1 'Barlow Condensed', system-ui, sans-serif; }
.ranking-record, .ranking-rate { color: var(--muted); font-size: 12px; }
.ranking-rate { color: white; font-weight: 700; }
.mobile-form { display: none; margin-top: 6px; }

.player-layout { display: grid; gap: 13px; }
.player-picker { display: flex; gap: 7px; overflow-x: auto; padding-bottom: 2px; scrollbar-width: none; }
.player-picker::-webkit-scrollbar { display: none; }
.player-picker button { flex: 0 0 auto; padding: 6px 11px 6px 7px; border: 1px solid var(--line); border-radius: 99px; background: #202a38; color: var(--muted); display: flex; align-items: center; gap: 6px; font: 750 14px/1 'Barlow Condensed', system-ui, sans-serif; }
.player-picker button.active { color: white; border-color: #4a83cf; background: #203d64; }
.player-hero { border-radius: 20px; padding: 19px; display: grid; grid-template-columns: auto 1fr auto; gap: 16px; align-items: center; border-color: #345a8c; background: #172338; }
.player-hero-copy { min-width: 0; }
.player-hero h2 { margin-bottom: 10px; }
.player-rank { text-align: right; display: grid; }
.player-rank span { color: var(--blue); font: 900 26px/1 'Barlow Condensed', system-ui, sans-serif; }
.player-rank strong { margin-top: 7px; font: 900 22px/1 'Barlow Condensed', system-ui, sans-serif; }
.player-rank small { color: var(--muted); font-size: 9px; letter-spacing: .12em; }
.goal-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.goal-grid div, .performance-split div, .context-split div { padding: 12px; border: 1px solid var(--line); border-radius: 12px; background: var(--panel-soft); display: grid; }
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
.versus-player { min-width: 0; display: flex; flex-direction: column; align-items: center; gap: 5px; }
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
  .recent-match-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
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
  .ranking-row { grid-template-columns: 32px minmax(0, 1fr) 62px 48px; padding: 12px 9px; }
  .ranking-record, .ranking-form { display: none; }
  .mobile-form { display: block; }
  .ranking-rate { text-align: right; }
  .ranking-elo { font-size: 15px; }
  .ranking-player { gap: 6px; }
  .player-hero { grid-template-columns: 72px minmax(0, 1fr) auto; gap: 10px; padding: 16px 12px; }
  .player-hero h2 { font-size: 29px; }
  .streak-card { grid-template-columns: repeat(2, 1fr); }
  .streak-card > div:nth-of-type(2) { border-right: 0; }
  .streak-card > div:nth-of-type(3), .streak-card > div:nth-of-type(4) { border-top: 1px solid var(--line); }
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; transition-duration: .01ms !important; }
}
</style>
