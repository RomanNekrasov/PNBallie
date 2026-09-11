import { onBeforeUnmount, watch, type ObjectDirective } from 'vue'
import { analyticsEnabled, trackStatsBlockView, type StatsBlock } from '../analytics'

type Observation = {
  block: StatsBlock
  observer?: IntersectionObserver
  resize?: ResizeObserver
  timer?: ReturnType<typeof setTimeout>
}

/** One qualified view per block during this mounted visit to statistics. */
export function useStatsBlockViews() {
  const seen = new Set<StatsBlock>()
  const observations = new Map<HTMLElement, Observation>()
  let disposed = false

  function cancel(record: Observation) {
    clearTimeout(record.timer)
    record.timer = undefined
  }

  function disconnect(record: Observation) {
    cancel(record)
    record.observer?.disconnect()
    record.observer = undefined
  }

  function visibleArea(rect: DOMRectReadOnly) {
    const height = Math.max(0, Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0))
    const width = Math.max(0, Math.min(rect.right, window.innerWidth) - Math.max(rect.left, 0))
    return width * height
  }

  function requiredArea(rect: DOMRectReadOnly) {
    // A long ranking table need not fit on screen: half a viewport is sufficient.
    return rect.width * Math.min(rect.height, window.innerHeight) / 2
  }

  function observe(element: HTMLElement, record: Observation) {
    disconnect(record)
    if (disposed || seen.has(record.block) || !analyticsEnabled.value
      || document.visibilityState !== 'visible' || !element.isConnected
      || typeof IntersectionObserver === 'undefined') return
    try {
      const rect = element.getBoundingClientRect()
      const threshold = rect.height > 0 ? Math.min(1, window.innerHeight / rect.height) / 2 : 0.5
      const observer = new IntersectionObserver(entries => {
        // Disconnect can leave an already queued callback; it must not restart a timer.
        if (record.observer !== observer || disposed || seen.has(record.block)) return
        for (const entry of entries) {
          const area = entry.intersectionRect.width * entry.intersectionRect.height
          const enough = entry.isIntersecting && entry.boundingClientRect.width > 0
            && entry.boundingClientRect.height > 0 && area >= requiredArea(entry.boundingClientRect)
            && document.visibilityState === 'visible'
          if (!enough) cancel(record)
          else if (record.timer === undefined) {
            record.timer = setTimeout(() => {
              record.timer = undefined
              const current = element.getBoundingClientRect()
              if (disposed || record.observer !== observer || !element.isConnected
                || document.visibilityState !== 'visible' || !analyticsEnabled.value
                || current.width <= 0 || current.height <= 0 || visibleArea(current) < requiredArea(current)) return
              seen.add(record.block)
              disconnect(record)
              record.resize?.disconnect()
              trackStatsBlockView(record.block)
            }, 2000)
          }
        }
      }, { threshold: [0, threshold] })
      record.observer = observer
      observer.observe(element)
    } catch { disconnect(record) /* Missing or blocked analytics APIs never affect the page. */ }
  }

  function resetStatsBlockViews() {
    for (const [element, record] of observations) observe(element, record)
  }

  function remove(element: HTMLElement) {
    const record = observations.get(element)
    if (!record) return
    disconnect(record)
    record.resize?.disconnect()
    observations.delete(element)
  }

  const vStatsBlock: ObjectDirective<HTMLElement, StatsBlock> = {
    mounted(element, { value: block }) {
      element.dataset.statsBlock = block
      const record: Observation = { block }
      observations.set(element, record)
      observe(element, record)
      if (typeof ResizeObserver !== 'undefined' && !seen.has(block)) {
        try {
          record.resize = new ResizeObserver(() => observe(element, record))
          record.resize.observe(element)
        } catch { /* Window resize still updates the visibility threshold. */ }
      }
    },
    beforeUnmount: remove,
  }

  watch(analyticsEnabled, resetStatsBlockViews)
  document.addEventListener('visibilitychange', resetStatsBlockViews)
  window.addEventListener('resize', resetStatsBlockViews, { passive: true })
  onBeforeUnmount(() => {
    disposed = true
    for (const element of observations.keys()) remove(element)
    document.removeEventListener('visibilitychange', resetStatsBlockViews)
    window.removeEventListener('resize', resetStatsBlockViews)
  })

  return { vStatsBlock, resetStatsBlockViews }
}
