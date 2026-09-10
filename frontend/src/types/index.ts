export interface Player {
  id: number
  name: string
  created_at: string
  group_id: number
  user_id: number | null
  is_active: boolean
  avatar_url: string | null
}

export interface MatchPlayerEntry {
  player_id: number
  side: 'orange' | 'blue'
  position: 'voor' | 'achter' | 'solo'
}

export interface Match {
  id: number
  orange_score: number
  blue_score: number
  played_at: string
  players: MatchPlayerEntry[]
}

export interface MatchCreate {
  orange_score: number
  blue_score: number
  players: MatchPlayerEntry[]
}

export type Position = 'orange_front' | 'orange_back' | 'blue_front' | 'blue_back'

export type StatsMode = 'all' | '1v1' | '2v2'
export type StatsPeriod = 'all' | '30d' | '50'

export interface PlayerBadge {
  key: string
  label: string
  emoji: string
  description: string
  earned_at: string
}

export interface PlayerStats {
  player_id: number
  name: string
  avatar_url?: string | null
  badges: PlayerBadge[]
  elo: number
  elo_precise: number
  rank: number | null
  matches: number
  wins: number
  losses: number
  winrate: number | null
  wins_1v1: number
  losses_1v1: number
  wins_2v2: number
  losses_2v2: number
  wins_orange: number
  matches_orange: number
  wins_blue: number
  matches_blue: number
  wins_voor: number
  matches_voor: number
  wins_achter: number
  matches_achter: number
  winrate_orange: number | null
  winrate_blue: number | null
  winrate_voor: number | null
  winrate_achter: number | null
  color_delta: number | null
  position_delta: number | null
  average_goals_for: number | null
  average_goals_against: number | null
  average_goal_difference: number | null
  recent_form: MatchResult[]
  biggest_victory_margin: number
  biggest_victory_score: string | null
  current_winstreak: number
  longest_winstreak: number
  current_losestreak: number
  longest_losestreak: number
}

export interface DayCount {
  day: string
  count: number
  before_14: number
  from_14: number
}

export interface GlobalStats {
  total_matches: number
  total_1v1: number
  total_2v2: number
  average_goals_per_match: number | null
  average_goal_difference: number | null
  orange_wins: number
  blue_wins: number
  orange_wins_1v1: number
  blue_wins_1v1: number
  orange_wins_2v2: number
  blue_wins_2v2: number
  current_orange_streak: number
  longest_orange_streak: number
  current_blue_streak: number
  longest_blue_streak: number
  lunch_matches: number
  middag_matches: number
  matches_per_day: DayCount[]
}

export interface LeaderboardEntry {
  player_id: number
  name: string
  avatar_url?: string | null
  elo: number
  elo_precise: number
  rank: number
  wins: number
  losses: number
  winrate: number
  recent_form: MatchResult[]
}

export type MatchResult = 'W' | 'L'

export interface HeadToHeadMatchup {
  player1_id: number
  player1_name: string
  player2_id: number
  player2_name: string
  player1_wins: number
  player2_wins: number
  total: number
}

export interface DuoStat {
  player1_id: number
  player1_name: string
  player2_id: number
  player2_name: string
  wins: number
  total: number
  winrate: number
}

export interface RecordItem {
  key: string
  label: string
  emoji: string
  description: string
  value: string
  detail: string
}

export interface StatsResponse {
  filters: { mode: StatsMode; period: StatsPeriod }
  players: PlayerStats[]
  global: GlobalStats
  leaderboard: LeaderboardEntry[]
  head_to_head: {
    matchups: HeadToHeadMatchup[]
    matchups_1v1: HeadToHeadMatchup[]
    matchups_2v2: HeadToHeadMatchup[]
    duos: DuoStat[]
  }
  records: RecordItem[]
  recent_matches: Match[]
}
