import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import GameIcon from './GameIcon.vue'
import { gameAssetUrl } from '../gameAssets'

const keys = [
  'first_win', 'win_streak_5', 'win_streak_10', 'matches_50', 'ijzeren_man',
  'dominant', 'koningspaar', 'rivalen', 'op_dreef', 'langste_reeks',
  'muurvast', 'doelpuntenmachine', 'grootste_afstraffing', 'streak_flame', 'football', 'clubhouse',
]

describe('selected game assets', () => {
  it('ships an image for every current badge, record and UI symbol', () => {
    for (const key of keys) expect(gameAssetUrl(key), key).toMatch(/\.webp(?:\?|$)/)
    expect(gameAssetUrl('unknown_future_badge')).toBeUndefined()
  })

  it('keeps decorative artwork out of the accessibility tree', () => {
    const wrapper = mount(GameIcon, { props: { asset: 'first_win' } })
    expect(wrapper.attributes('aria-hidden')).toBe('true')
    expect(wrapper.get('img').attributes('alt')).toBe('')
  })

  it('announces the active winning streak when the icon carries meaning', () => {
    const wrapper = mount(GameIcon, { props: { asset: 'streak_flame', label: '4 overwinningen op rij' } })
    expect(wrapper.attributes('role')).toBe('img')
    expect(wrapper.attributes('aria-label')).toBe('4 overwinningen op rij')
    expect(wrapper.attributes('aria-hidden')).toBeUndefined()
  })

  it('uses the legacy fallback on load failure and recovers when the asset changes', async () => {
    const wrapper = mount(GameIcon, { props: { asset: 'first_win', fallback: '⭐' } })
    await wrapper.get('img').trigger('error')
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.text()).toBe('⭐')
    await wrapper.setProps({ asset: 'football' })
    expect(wrapper.find('img').exists()).toBe(true)
  })
})
