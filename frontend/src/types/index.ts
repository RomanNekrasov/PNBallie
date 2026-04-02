export interface Player {
  id: number
  name: string
  created_at: string
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

export interface PlayerStats {
  player_id: number
  name: string
  wins: number
  losses: number
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
  biggest_victory_margin: number
  current_winstreak: number
  longest_winstreak: number
  current_losestreak: number
  longest_losestreak: number
}

export interface DayCount {
  day: string
  count: number
}

export interface GlobalStats {
  total_matches: number
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

export interface StatsResponse {
  players: PlayerStats[]
  global: GlobalStats
}
