import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PlayerSelectModal from './PlayerSelectModal.vue'
import MatchHistoryModal from './MatchHistoryModal.vue'
import type { Player } from '../types'

const players = [{ id: 1, name: 'Ada' }, { id: 2, name: 'Bo' }] as Player[]
function selection() {
  return mount(PlayerSelectModal, {
    props: { open: true, players, currentPlayerId: null, position: 'orange_front', leaderPlayerIds: [],
      selectedPlayers: { orange_front: null, orange_back: null, blue_front: 2, blue_back: null } },
    global: { stubs: { teleport: true } },
  })
}
function history() {
  return mount(MatchHistoryModal, {
    props: { open: true, players, canDelete: true, matches: [{
      id: 8, orange_score: 10, blue_score: 7, played_at: '2026-09-17T12:00:00Z',
      players: [{ player_id: 1, side: 'orange', position: 'solo' }, { player_id: 2, side: 'blue', position: 'solo' }],
    }] },
    global: { stubs: { teleport: true } },
  })
}

describe('dismiss overlays from non-interactive areas', () => {
  it.each([selection, history])('closes from the full-height content area', async (create) => {
    const wrapper = create()
    await wrapper.get('.overflow-y-auto').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
    wrapper.unmount()
  })

  it('still selects a player and closes exactly once', async () => {
    const wrapper = selection()
    await wrapper.get('.choice-name').trigger('click')
    expect(wrapper.emitted('select')).toEqual([[1]])
    expect(wrapper.emitted('close')).toHaveLength(1)
    wrapper.unmount()
  })

  it('does not close when tapping content inside a disabled player button', async () => {
    const wrapper = selection()
    await wrapper.get('button:disabled .choice-name').trigger('click')
    expect(wrapper.emitted('close')).toBeUndefined()
    expect(wrapper.emitted('select')).toBeUndefined()
    wrapper.unmount()
  })

  it('keeps the history open when deleting, but closes when tapping a result', async () => {
    const wrapper = history()
    await wrapper.get('button svg').trigger('click')
    expect(wrapper.emitted('delete')).toEqual([[8]])
    expect(wrapper.emitted('close')).toBeUndefined()
    await wrapper.get('.history-score').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
    wrapper.unmount()
  })
})
