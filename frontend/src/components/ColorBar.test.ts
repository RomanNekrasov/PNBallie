import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ColorBar from './ColorBar.vue'

describe('wins per colour', () => {
  it.each([
    [4, 1, 'orange', 'Oranje leidt'],
    [1, 4, 'blue', 'Blauw leidt'],
    [3, 3, 'tie', 'Gelijke stand'],
    [0, 0, 'tie', 'Nog geen wedstrijden'],
  ] as const)('shows the lead or tie for %i–%i', (orange, blue, marker, explanation) => {
    const wrapper = mount(ColorBar, { props: { label: '2v2', orange, blue } })
    expect(wrapper.get('.leader-dot').classes()).toContain(marker)
    expect(wrapper.get('.bar-line').attributes('aria-label')).toBe(`2v2: ${explanation}`)
    expect(wrapper.text()).toContain(explanation)
    if (orange + blue === 0) expect(wrapper.text()).not.toContain('50%')
  })
})
