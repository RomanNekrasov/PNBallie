import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PlayerFlames from './PlayerFlames.vue'
import PlayerBox from './PlayerBox.vue'
import StatsPlayerAvatar from './StatsPlayerAvatar.vue'

describe('current winning streak flames', () => {
  it.each([0, 3, 4, 5, 10])('shows flames only from five wins (%i)', (winStreak) => {
    const wrapper = mount(PlayerFlames, { props: { winStreak } })
    expect(wrapper.find('.player-flames').exists()).toBe(winStreak >= 5)
    if (winStreak >= 5) {
      expect(wrapper.attributes('aria-label')).toBe(`${winStreak} overwinningen op rij`)
      expect(wrapper.findAll('img')).toHaveLength(2)
    }
  })

  it('updates with the player and coexists with the crown on the field', async () => {
    const wrapper = mount(PlayerBox, { props: {
      team: 'orange', label: 'Voor', position: 'orange_front',
      playerId: 1, playerName: 'Roman', playerAvatar: '/avatars/roman.png',
      crowned: true, winStreak: 5,
    } })
    expect(wrapper.find('.player-flames').exists()).toBe(true)
    expect(wrapper.find('.crown-icon').exists()).toBe(true)
    await wrapper.setProps({ playerId: 2, playerName: 'Ada', crowned: false, winStreak: 4 })
    expect(wrapper.find('.player-flames').exists()).toBe(false)
    expect(wrapper.find('.crown-icon').exists()).toBe(false)
  })

  it('removes flames after a loss while keeping the number-one crown', async () => {
    const wrapper = mount(StatsPlayerAvatar, { props: { name: 'Roman', crowned: true, winStreak: 5 } })
    expect(wrapper.find('.player-flames').exists()).toBe(true)
    await wrapper.setProps({ winStreak: 0 })
    expect(wrapper.find('.player-flames').exists()).toBe(false)
    expect(wrapper.find('.crown-icon').exists()).toBe(true)
  })
})
