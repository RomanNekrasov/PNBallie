import { computed } from 'vue'
import { currentGroup } from '../auth'
import { defaultTableSettings, teamColors, type TeamSide } from '../tableSettings'

export function useTableSettings() {
  const tableSettings = computed(() => ({ ...defaultTableSettings, ...currentGroup.value?.table_settings }))
  const teamName = (side: TeamSide) => teamColors[tableSettings.value[`${side}_color`]].label
  return { tableSettings, teamName }
}
