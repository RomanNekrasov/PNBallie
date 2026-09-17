export const teamColors = {
  orange: { label: 'Oranje', color: '#e87d2f', dark: '#9f4f1e', text: '#ffc18b', accent: '#ff7a2f' },
  blue: { label: 'Blauw', color: '#2d5fa1', dark: '#244f86', text: '#89b2de', accent: '#3b8cff' },
  red: { label: 'Rood', color: '#d54444', dark: '#8b2929', text: '#ffa3a3', accent: '#ff6262' },
  green: { label: 'Groen', color: '#2e9b65', dark: '#1d6441', text: '#87dfb0', accent: '#43ce89' },
  yellow: { label: 'Geel', color: '#edc638', dark: '#756016', text: '#ffe781', accent: '#f1cf3c' },
  purple: { label: 'Paars', color: '#9560d0', dark: '#60388b', text: '#d2b0ff', accent: '#b07aff' },
  black: { label: 'Zwart', color: '#272b33', dark: '#171b22', text: '#aeb8c8', accent: '#aeb8c8' },
  white: { label: 'Wit', color: '#eeeeec', dark: '#52565e', text: '#ffffff', accent: '#ffffff' },
} as const
export type TeamSide = 'orange' | 'blue'
export interface TableSettings {
  orange_color: keyof typeof teamColors
  blue_color: keyof typeof teamColors
  field_color: string
  rim_color: string
  score_position: 'own_goal' | 'opponent_goal'
}
export const defaultTableSettings: TableSettings = {
  orange_color: 'orange', blue_color: 'blue', field_color: '#2d6a30', rim_color: '#5a3a1a', score_position: 'opponent_goal',
}
export function tableVariables(settings: TableSettings): Record<string, string> {
  const result: Record<string, string> = { '--table-field': settings.field_color, '--table-rim': settings.rim_color }
  const channels = [1, 3, 5].map(start => parseInt(settings.field_color.slice(start, start + 2), 16))
  const lightField = channels[0]! * .299 + channels[1]! * .587 + channels[2]! * .114 > 160
  result['--table-lines'] = lightField ? 'rgba(0,0,0,.3)' : 'rgba(255,255,255,.25)'
  result['--table-ball'] = lightField ? '#28313c' : '#f5f5f0'
  for (const side of ['orange', 'blue'] as const) {
    const color = teamColors[settings[`${side}_color`]]
    result[`--team-${side}`] = color.color
    result[`--team-${side}-dark`] = color.dark
    result[`--team-${side}-text`] = color.text
    result[`--team-${side}-accent`] = color.accent
  }
  return result
}
export function scoreSideAtTop(settings: TableSettings): TeamSide {
  return settings.score_position === 'own_goal' ? 'blue' : 'orange'
}
