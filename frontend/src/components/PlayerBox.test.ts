import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import PlayerBox from './PlayerBox.vue'

function pointerEvent(
  type: string,
  options: { pointerId?: number; pointerType?: string; clientX?: number; clientY?: number } = {},
) {
  const event = new Event(type, { bubbles: true, cancelable: true })
  Object.defineProperties(event, {
    pointerId: { value: options.pointerId ?? 1 },
    pointerType: { value: options.pointerType ?? 'touch' },
    clientX: { value: options.clientX ?? 0 },
    clientY: { value: options.clientY ?? 0 },
  })
  return event
}

function mountPlayer(): VueWrapper {
  return mount(PlayerBox, {
    attachTo: document.body,
    props: {
      team: 'orange',
      label: 'Voor',
      playerId: 1,
      playerName: 'Ada',
      playerAvatar: null,
      position: 'orange_front',
    },
  })
}

describe('PlayerBox touch pointer interaction', () => {
  beforeEach(() => {
    Object.defineProperties(HTMLElement.prototype, {
      setPointerCapture: { configurable: true, value: vi.fn() },
      hasPointerCapture: { configurable: true, value: vi.fn(() => false) },
      releasePointerCapture: { configurable: true, value: vi.fn() },
    })
  })

  afterEach(() => {
    document.body.innerHTML = ''
    vi.restoreAllMocks()
  })

  it('keeps a simple touch as a tap', async () => {
    const wrapper = mountPlayer()
    wrapper.element.dispatchEvent(pointerEvent('pointerdown', { clientX: 20, clientY: 20 }))
    wrapper.element.dispatchEvent(pointerEvent('pointerup', { clientX: 20, clientY: 20 }))
    await wrapper.trigger('click')

    expect(wrapper.emitted('tap')).toHaveLength(1)
    expect(wrapper.emitted('dragstart')).toBeUndefined()
  })

  it('does not drag below the eight-pixel movement threshold', async () => {
    const wrapper = mountPlayer()
    wrapper.element.dispatchEvent(pointerEvent('pointerdown', { clientX: 10, clientY: 10 }))
    wrapper.element.dispatchEvent(pointerEvent('pointermove', { clientX: 16, clientY: 14 }))
    wrapper.element.dispatchEvent(pointerEvent('pointerup', { clientX: 16, clientY: 14 }))
    await wrapper.trigger('click')

    expect(wrapper.emitted('tap')).toHaveLength(1)
    expect(wrapper.emitted('dropped')).toBeUndefined()
  })

  it('starts immediately after the threshold and swaps with an empty destination', () => {
    const wrapper = mountPlayer()
    const destination = document.createElement('div')
    destination.dataset.position = 'blue_back'
    document.body.appendChild(destination)
    vi.spyOn(document, 'elementFromPoint').mockReturnValue(destination)

    wrapper.element.dispatchEvent(pointerEvent('pointerdown', { clientX: 10, clientY: 10 }))
    wrapper.element.dispatchEvent(pointerEvent('pointermove', { clientX: 19, clientY: 10 }))
    wrapper.element.dispatchEvent(pointerEvent('pointerup', { clientX: 30, clientY: 30 }))

    expect(wrapper.emitted('dragstart')).toEqual([["orange_front"]])
    expect(wrapper.emitted('dropped')).toEqual([["orange_front", "blue_back"]])
    expect(wrapper.emitted('dragend')).toHaveLength(1)
    expect(document.querySelector('.touch-drag-ghost')).toBeNull()
    expect(destination.classList.contains('player-drop-target')).toBe(false)
  })

  it('cancels cleanly without swapping or leaving visual state', () => {
    const wrapper = mountPlayer()
    const destination = document.createElement('div')
    destination.dataset.position = 'orange_back'
    document.body.appendChild(destination)
    vi.spyOn(document, 'elementFromPoint').mockReturnValue(destination)

    wrapper.element.dispatchEvent(pointerEvent('pointerdown'))
    wrapper.element.dispatchEvent(pointerEvent('pointermove', { clientX: 20 }))
    expect(document.querySelector('.touch-drag-ghost')).not.toBeNull()
    expect(destination.classList.contains('player-drop-target')).toBe(true)

    wrapper.element.dispatchEvent(pointerEvent('pointercancel', { clientX: 20 }))

    expect(wrapper.emitted('dropped')).toBeUndefined()
    expect(wrapper.emitted('dragend')).toHaveLength(1)
    expect(document.querySelector('.touch-drag-ghost')).toBeNull()
    expect(destination.classList.contains('player-drop-target')).toBe(false)
  })
})
