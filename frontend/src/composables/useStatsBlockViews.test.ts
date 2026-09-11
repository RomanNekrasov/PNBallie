import { mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, ref, withDirectives } from 'vue'
import { useStatsBlockViews } from './useStatsBlockViews'

const { track } = vi.hoisted(() => ({ track: vi.fn() }))
vi.mock('../analytics', () => ({ analyticsEnabled: ref(true), trackStatsBlockView: track }))
import { analyticsEnabled } from '../analytics'
const enabled = analyticsEnabled as { value: boolean }

class TestIntersectionObserver {
  static instances: TestIntersectionObserver[] = []
  target?: HTMLElement
  active = false
  callback: IntersectionObserverCallback
  options: IntersectionObserverInit
  constructor(callback: IntersectionObserverCallback, options: IntersectionObserverInit) {
    this.callback = callback
    this.options = options
    TestIntersectionObserver.instances.push(this)
  }
  observe(target: HTMLElement) { this.target = target; this.active = true }
  disconnect() { this.active = false }
  report(fraction: number) {
    const rect = this.target!.getBoundingClientRect()
    this.callback([{
      target: this.target!, isIntersecting: fraction > 0, intersectionRatio: fraction,
      boundingClientRect: rect, intersectionRect: new DOMRect(rect.x, rect.y, rect.width, rect.height * fraction),
      rootBounds: new DOMRect(0, 0, window.innerWidth, window.innerHeight), time: performance.now(),
    }], this as unknown as IntersectionObserver)
  }
}
class TestResizeObserver {
  static instances: TestResizeObserver[] = []
  active = false
  callback: () => void
  constructor(callback: () => void) { this.callback = callback; TestResizeObserver.instances.push(this) }
  observe() { this.active = true }
  disconnect() { this.active = false }
}

const Fixture = defineComponent({
  setup() {
    const showRanking = ref(true)
    const { vStatsBlock, resetStatsBlockViews } = useStatsBlockViews()
    return { showRanking, vStatsBlock, resetStatsBlockViews }
  },
  render() {
    return h('section', [withDirectives(
      h('article', { key: this.showRanking ? 'ranking' : 'activity' }, this.showRanking ? 'Ranking' : 'Activity'),
      [[this.vStatsBlock, this.showRanking ? 'ranking' : 'activity']],
    )])
  },
})
let wrappers: VueWrapper[]
let elementRect: DOMRect

beforeEach(() => {
  vi.useFakeTimers()
  wrappers = []
  elementRect = new DOMRect(0, 100, 300, 200)
  TestIntersectionObserver.instances = []
  TestResizeObserver.instances = []
  vi.stubGlobal('IntersectionObserver', TestIntersectionObserver)
  vi.stubGlobal('ResizeObserver', TestResizeObserver)
  Object.defineProperty(window, 'innerHeight', { value: 800, configurable: true })
  Object.defineProperty(window, 'innerWidth', { value: 400, configurable: true })
  Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(() => elementRect)
  enabled.value = true
  track.mockClear()
})
afterEach(() => {
  wrappers.forEach(wrapper => wrapper.unmount())
  vi.useRealTimers()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  Reflect.deleteProperty(document, 'visibilityState')
  document.body.innerHTML = ''
})
function open() {
  const wrapper = mount(Fixture, { attachTo: document.body })
  wrappers.push(wrapper)
  return wrapper
}
function observer() {
  return TestIntersectionObserver.instances.filter(instance => instance.active).slice(-1)[0]!
}
function changeVisibility(value: 'hidden' | 'visible') {
  Object.defineProperty(document, 'visibilityState', { value, configurable: true })
  document.dispatchEvent(new Event('visibilitychange'))
}

describe('statistics block views', () => {
  it('requires two continuous seconds with at least half the block visible', async () => {
    const wrapper = open()
    expect(wrapper.get('article').attributes('data-stats-block')).toBe('ranking')
    observer().report(0.49)
    await vi.advanceTimersByTimeAsync(3000)
    expect(track).not.toHaveBeenCalled()
    observer().report(0.5)
    await vi.advanceTimersByTimeAsync(1999)
    expect(track).not.toHaveBeenCalled()
    observer().report(0.49)
    await vi.advanceTimersByTimeAsync(1)
    expect(track).not.toHaveBeenCalled()
    observer().report(0.5)
    await vi.advanceTimersByTimeAsync(2000)
    expect(track).toHaveBeenCalledExactlyOnceWith('ranking')
  })

  it('qualifies tall ranking tables after half a viewport is visible and adapts after resize', async () => {
    elementRect = new DOMRect(0, 0, 300, 2400)
    open()
    expect(observer().options.threshold).toEqual([0, 1 / 6])
    observer().report(1 / 6)
    await vi.advanceTimersByTimeAsync(1500)
    Object.defineProperty(window, 'innerHeight', { value: 1200, configurable: true })
    window.dispatchEvent(new Event('resize'))
    expect(observer().options.threshold).toEqual([0, 0.25])
    observer().report(1 / 6)
    await vi.advanceTimersByTimeAsync(3000)
    expect(track).not.toHaveBeenCalled()
    observer().report(0.25)
    await vi.advanceTimersByTimeAsync(2000)
    expect(track).toHaveBeenCalledExactlyOnceWith('ranking')
  })

  it('does not count a background tab and starts a fresh interval when it becomes visible', async () => {
    open()
    const old = observer()
    old.report(1)
    await vi.advanceTimersByTimeAsync(1500)
    changeVisibility('hidden')
    old.report(1) // A browser may already have queued this disconnected callback.
    await vi.advanceTimersByTimeAsync(5000)
    expect(track).not.toHaveBeenCalled()
    changeVisibility('visible')
    observer().report(1)
    await vi.advanceTimersByTimeAsync(1999)
    expect(track).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(track).toHaveBeenCalledExactlyOnceWith('ranking')
  })

  it('deduplicates remounted blocks and filter/player changes within one statistics visit', async () => {
    const wrapper = open()
    observer().report(1)
    await vi.advanceTimersByTimeAsync(2000)
    wrapper.vm.showRanking = false
    await nextTick()
    observer().report(1)
    await vi.advanceTimersByTimeAsync(2000)
    wrapper.vm.showRanking = true
    await nextTick()
    wrapper.vm.resetStatsBlockViews()
    await vi.advanceTimersByTimeAsync(5000)
    expect(track.mock.calls).toEqual([['ranking'], ['activity']])
    expect(TestIntersectionObserver.instances.filter(instance => instance.active)).toHaveLength(0)
  })

  it('resets a pending interval when the displayed filter/player content changes', async () => {
    const wrapper = open()
    const old = observer()
    old.report(1)
    await vi.advanceTimersByTimeAsync(1500)
    wrapper.vm.resetStatsBlockViews()
    old.report(1)
    observer().report(1)
    await vi.advanceTimersByTimeAsync(1999)
    expect(track).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(track).toHaveBeenCalledExactlyOnceWith('ranking')
  })

  it('cancels pending views on tab removal or route unmount; a new visit can count again', async () => {
    const first = open()
    const stale = observer()
    stale.report(1)
    await vi.advanceTimersByTimeAsync(1500)
    first.vm.showRanking = false
    await nextTick()
    stale.report(1)
    await vi.advanceTimersByTimeAsync(500)
    expect(track).not.toHaveBeenCalled()
    observer().report(1)
    first.unmount()
    await vi.advanceTimersByTimeAsync(3000)
    expect(track).not.toHaveBeenCalled()
    open()
    observer().report(1)
    await vi.advanceTimersByTimeAsync(2000)
    expect(track).toHaveBeenCalledExactlyOnceWith('ranking')
    expect(TestResizeObserver.instances.slice(0, 2).every(instance => !instance.active)).toBe(true)
  })

  it('rechecks the viewport when the timer fires even if an intersection callback is delayed', async () => {
    open()
    observer().report(1)
    elementRect = new DOMRect(0, 900, 300, 200)
    await vi.advanceTimersByTimeAsync(2000)
    expect(track).not.toHaveBeenCalled()
  })

  it('reobserves resized content and stops observing a block after its view is counted', async () => {
    open()
    observer().report(1)
    await vi.advanceTimersByTimeAsync(1500)
    TestResizeObserver.instances[0]!.callback()
    observer().report(1)
    await vi.advanceTimersByTimeAsync(1999)
    expect(track).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(track).toHaveBeenCalledExactlyOnceWith('ranking')
    expect(TestResizeObserver.instances[0]!.active).toBe(false)
    expect(TestIntersectionObserver.instances.every(instance => !instance.active)).toBe(true)
  })

  it('remains optional when runtime analytics is disabled, then starts when configuration arrives', async () => {
    enabled.value = false
    open()
    expect(TestIntersectionObserver.instances).toHaveLength(0)
    enabled.value = true
    await nextTick()
    observer().report(1)
    await vi.advanceTimersByTimeAsync(2000)
    expect(track).toHaveBeenCalledExactlyOnceWith('ranking')
  })

  it('leaves the statistics usable when IntersectionObserver is unavailable', async () => {
    vi.stubGlobal('IntersectionObserver', undefined)
    const wrapper = open()
    expect(wrapper.text()).toContain('Ranking')
    await vi.advanceTimersByTimeAsync(3000)
    expect(track).not.toHaveBeenCalled()
  })
})
