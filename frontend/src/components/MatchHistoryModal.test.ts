import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MatchHistoryModal from './MatchHistoryModal.vue'
import type { Match, Player } from '../types'

describe('recent match score placement', () => {
  it('places a 2v2 score between both teams and includes its timestamp', () => {
    const players = [
      { id: 1, name: 'Ada' }, { id: 2, name: 'Bo' }, { id: 3, name: 'Cleo' }, { id: 4, name: 'Daan' },
    ] as Player[]
    const matches: Match[] = [{
      id: 1, orange_score: 10, blue_score: 4, played_at: '2026-07-01T12:00:00Z',
      players: [
        { player_id: 1, side: 'orange', position: 'voor' },
        { player_id: 2, side: 'orange', position: 'achter' },
        { player_id: 3, side: 'blue', position: 'voor' },
        { player_id: 4, side: 'blue', position: 'achter' },
      ],
    }]
    const wrapper = mount(MatchHistoryModal, {
      props: { open: true, matches, players, canDelete: false },
      global: { stubs: { teleport: true } },
    })
    const order = Array.from(wrapper.get('.history-result').element.children)
    expect(order[0]?.textContent).toContain('Ada & Bo')
    expect(order[1]?.classList.contains('history-score')).toBe(true)
    expect(order[2]?.textContent).toContain('Cleo & Daan')
    expect(wrapper.get('time').attributes('datetime')).toBe('2026-07-01T12:00:00Z')
  })
})
