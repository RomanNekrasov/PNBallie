import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, ref, type EffectScope } from 'vue'
import { currentGroup } from '../auth'
import { api } from './useApi'
import { useStats } from './useStats'
import type { StatsResponse } from '../types'

vi.mock('./useApi', () => ({ api: vi.fn() }))
vi.mock('../auth', () => ({ currentGroup: ref({ id: 1, player_id: 1 }) }))

let scope: EffectScope | undefined
afterEach(() => {
  scope?.stop()
  vi.resetAllMocks()
})

function setup() {
  scope = effectScope()
  return scope.run(() => useStats())!
}

describe('statistics selection and request ordering', () => {
  it('sends both selected filters to the API', async () => {
    vi.mocked(api).mockResolvedValue({ filters: { mode: '2v2', period: '50' } })
    const state = setup()
    state.mode.value = '2v2'
    state.period.value = '50'
    await state.fetchStats()
    expect(api).toHaveBeenCalledWith('/api/stats?mode=2v2&period=50')
    expect(state.stats.value?.filters).toEqual({ mode: '2v2', period: '50' })
  })

  it('keeps the latest filter result when an older request finishes late', async () => {
    let finishOld!: (value: StatsResponse) => void
    vi.mocked(api).mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve as typeof finishOld }))
    const state = setup()
    const oldRequest = state.fetchStats()
    state.mode.value = '1v1'
    vi.mocked(api).mockResolvedValueOnce({ filters: { mode: '1v1', period: 'all' } })
    await state.fetchStats()
    finishOld({ filters: { mode: 'all', period: 'all' } } as StatsResponse)
    await oldRequest
    expect(state.stats.value?.filters.mode).toBe('1v1')
  })

  it('clears previous group data immediately and ignores requests from that group', async () => {
    let finishOld!: (value: StatsResponse) => void
    vi.mocked(api).mockResolvedValueOnce({ filters: { mode: 'all', period: 'all' } })
    const state = setup()
    await state.fetchStats()
    expect(state.stats.value).not.toBeNull()
    vi.mocked(api).mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve as typeof finishOld }))
    const oldRequest = state.fetchStats()
    // The actual export is computed; the module mock is deliberately mutable.
    ;(currentGroup as unknown as ReturnType<typeof ref>).value = { id: 2, player_id: 3 }
    expect(state.stats.value).toBeNull()
    finishOld({ filters: { mode: 'all', period: 'all' } } as StatsResponse)
    await oldRequest
    expect(state.stats.value).toBeNull()
    expect(state.loading.value).toBe(false)
  })
})
