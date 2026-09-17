import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'
import BadgeHelp from './BadgeHelp.vue'

let wrapper: ReturnType<typeof mount>
afterEach(() => wrapper?.unmount())
function setup() {
  wrapper = mount(BadgeHelp, { attachTo: document.body, props: {
    label: 'Dominant', description: 'Hoogste winrate (min. 10 wedstrijden).',
  } })
  return wrapper
}

describe('badge explanations', () => {
  it('opens and closes by tap and links the explanation to its button', async () => {
    const view = setup()
    const button = view.get('button')
    expect(button.attributes('aria-label')).toBe('Uitleg over Dominant')
    expect(button.attributes('aria-expanded')).toBe('false')
    await button.trigger('pointerdown', { pointerType: 'touch' })
    await button.trigger('click', { detail: 1 })
    expect(view.get('[role="note"]').text()).toContain('min. 10 wedstrijden')
    expect(button.attributes('aria-describedby')).toBe(view.get('[role="note"]').attributes('id'))
    await button.trigger('pointerdown', { pointerType: 'touch' })
    await button.trigger('click', { detail: 1 })
    expect(view.find('[role="note"]').exists()).toBe(false)
  })

  it('shows on mouse hover without pinning on click, but does not simulate hover for touch', async () => {
    const view = setup()
    await view.trigger('pointerenter', { pointerType: 'touch' })
    expect(view.find('[role="note"]').exists()).toBe(false)
    await view.trigger('pointerenter', { pointerType: 'mouse' })
    expect(view.find('[role="note"]').exists()).toBe(true)
    await view.get('button').trigger('pointerdown', { pointerType: 'mouse' })
    await view.get('button').trigger('click', { detail: 1 })
    expect(view.find('[role="note"]').exists()).toBe(true)
    await view.trigger('pointerleave')
    expect(view.find('[role="note"]').exists()).toBe(false)
    await view.get('button').trigger('click', { detail: 1 })
    expect(view.find('[role="note"]').exists()).toBe(false)
  })

  it.each(['pointerdown', 'touchstart'])('recognizes a touch followed by a mouse-compatible click (%s)', async (start) => {
    const view = setup()
    const button = view.get('button')
    await button.trigger(start, { pointerType: 'touch' })
    await button.trigger('click', { detail: 1, pointerType: 'mouse' })
    expect(button.attributes('aria-expanded')).toBe('true')
    expect(view.get('[role="note"]').text()).toContain('min. 10 wedstrijden')
    await button.trigger(start, { pointerType: 'touch' })
    await button.trigger('click', { detail: 1, pointerType: 'mouse' })
    expect(view.find('[role="note"]').exists()).toBe(false)
    // A real mouse on the same device must still remain hover-only.
    await button.trigger('pointerdown', { pointerType: 'mouse' })
    await button.trigger('click', { detail: 1, pointerType: 'mouse' })
    expect(view.find('[role="note"]').exists()).toBe(false)
  })

  it('dismisses a pinned explanation with Escape, outside click, focus leaving or scrolling', async () => {
    const view = setup()
    for (const dismiss of [
      () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })),
      () => document.body.dispatchEvent(new Event('pointerdown', { bubbles: true })),
      () => view.trigger('focusout', { relatedTarget: null }),
      () => window.dispatchEvent(new Event('scroll')),
      () => view.element.dispatchEvent(new Event('scroll')),
    ]) {
      await view.get('button').trigger('click')
      await view.trigger('pointerleave')
      expect(view.find('[role="note"]').exists()).toBe(true)
      await dismiss()
      await view.vm.$nextTick()
      expect(view.find('[role="note"]').exists()).toBe(false)
    }
  })
})
