import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const websiteId = '03c9b13b-4507-517c-b008-c488152a163b'
let analytics: typeof import('./analytics')
const configResponse = (analytics: unknown) => new Response(JSON.stringify({ analytics }))

beforeEach(async () => {
  vi.resetModules()
  vi.useFakeTimers()
  localStorage.clear()
  Object.defineProperty(navigator, 'doNotTrack', { value: '0', configurable: true })
  Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
  delete window.umami
  const append = document.head.appendChild.bind(document.head)
  vi.spyOn(document.head, 'appendChild').mockImplementation(<T extends Node>(node: T): T => {
    if (node instanceof HTMLScriptElement) node.type = 'text/plain' // Never execute or fetch third-party code in a unit test.
    return append(node)
  })
  analytics = await import('./analytics')
})
afterEach(() => {
  analytics.disposeAnalytics()
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  Reflect.deleteProperty(navigator, 'doNotTrack')
  Reflect.deleteProperty(document, 'visibilityState')
  document.getElementById('pnballie-analytics')?.remove()
})

async function enable() {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(configResponse({ enabled: true, websiteId })))
  await analytics.initAnalytics()
  const script = document.getElementById('pnballie-analytics') as HTMLScriptElement
  const track = vi.fn().mockResolvedValue(undefined)
  window.umami = { track }
  script.dispatchEvent(new Event('load'))
  return { script, track }
}

describe('allowlisted Umami analytics', () => {
  it('does nothing by default and never loads a tracker when runtime analytics is disabled', async () => {
    const fetchMock = vi.fn().mockResolvedValue(configResponse({ enabled: false, websiteId: '' }))
    vi.stubGlobal('fetch', fetchMock)
    analytics.trackScreen('game')
    analytics.trackEvent('match_saved', { mode: '1v1' })
    expect(fetchMock).not.toHaveBeenCalled()
    await analytics.initAnalytics()
    expect(document.getElementById('pnballie-analytics')).toBeNull()
    expect(analytics.analyticsEnabled.value).toBe(false)
  })

  it('respects Do Not Track before config, tracker or event requests', async () => {
    Object.defineProperty(navigator, 'doNotTrack', { value: '1', configurable: true })
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    await analytics.initAnalytics()
    analytics.trackScreen('profile')
    analytics.trackEvent('avatar_queued', { provider: 'local' })
    expect(fetchMock).not.toHaveBeenCalled()
    expect(document.getElementById('pnballie-analytics')).toBeNull()
  })

  it('fails open when config is unavailable or attempts to configure an external collector', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(configResponse({ enabled: true, websiteId: 'https://external.test' })))
    await expect(analytics.initAnalytics()).resolves.toBeUndefined()
    expect(document.getElementById('pnballie-analytics')).toBeNull()
  })

  it('loads the same-origin tracker with all automatic collection disabled', async () => {
    const { script } = await enable()
    expect(script.getAttribute('src')).toBe('/analytics/script.js')
    expect(script.dataset.autoTrack).toBe('false')
    expect(script.dataset.autoPageview).toBe('false')
    expect(script.dataset.performance).toBe('false')
    expect(script.dataset.doNotTrack).toBe('true')
    expect(script.dataset.hostUrl).toBe(`${window.location.origin}/analytics`)
    expect(script.referrerPolicy).toBe('no-referrer')
  })

  it('measures virtual tab screens and actions without including real URLs or identifiers', async () => {
    const { track } = await enable()
    analytics.trackScreen('stats_overview')
    analytics.trackScreen('stats_players')
    analytics.trackScreen('stats_players')
    analytics.trackEvent('stats_filters_changed', { mode: '2v2', period: '30d', player_id: 912, email: 'private@example.test', code: 'invite-secret' })
    expect(track).toHaveBeenCalledTimes(3)
    expect(track.mock.calls[1]?.[0]).toMatchObject({ url: '/app/stats_players', title: 'Statistieken · spelers', referrer: '' })
    expect(track.mock.calls[2]?.[0].data).toEqual({ mode: '2v2', period: '30d' })
    expect(JSON.stringify(track.mock.calls)).not.toMatch(/private@example|invite-secret|912|player_id/)
  })

  it('rebuilds payloads at the before-send boundary and rejects unknown screens/types/events/values', async () => {
    await enable()
    const input = { website: 'attacker', url: '/app/groups', title: 'Private Group', referrer: '/join/secret', id: 'person-id', name: 'group_joined', data: { code: 'secret', name: 'Ada' } }
    expect(window.pnballieAnalyticsBeforeSend?.('event', input)).toEqual({
      website: websiteId, hostname: location.hostname, url: '/app/groups', title: 'Groepen', referrer: '', language: navigator.language,
      name: 'group_joined',
    })
    expect(window.pnballieAnalyticsBeforeSend?.('identify', input)).toBeNull()
    expect(window.pnballieAnalyticsBeforeSend?.('event', { ...input, url: '/join/secret' })).toBeNull()
    expect(window.pnballieAnalyticsBeforeSend?.('event', { ...input, name: 'private-email' })).toBeNull()
    expect(window.pnballieAnalyticsBeforeSend?.('event', { ...input, name: 'avatar_queued', data: { provider: 'private-email' } })).toBeNull()
  })

  it('tracks a visible interval without collecting pointer, keystroke or session replay data', async () => {
    const { track } = await enable()
    analytics.trackScreen('game')
    await vi.advanceTimersByTimeAsync(29_999)
    expect(track).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(track.mock.calls[1]?.[0]).toMatchObject({ url: '/app/game', name: 'screen_visible_30s' })
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(60_000)
    expect(track).toHaveBeenCalledTimes(2)
  })

  it('never lets a blocked or throwing tracker interrupt successful application actions', async () => {
    const { track } = await enable()
    track.mockImplementation(() => { throw new Error('blocked') })
    expect(() => analytics.trackScreen('game')).not.toThrow()
    expect(() => analytics.trackEvent('match_saved', { mode: '1v1' })).not.toThrow()
  })

  it('attributes a viewed statistics block to its fixed screen and strips selected-player data', async () => {
    const { track } = await enable()
    analytics.trackScreen('game')
    analytics.trackStatsBlockView('player_goals')
    expect(track.mock.calls[1]?.[0]).toMatchObject({
      url: '/app/stats_players', name: 'stats_block_viewed', data: { block: 'player_goals' },
    })
    expect(window.pnballieAnalyticsBeforeSend?.('event', {
      url: '/app/stats_players', name: 'stats_block_viewed',
      data: { block: 'player_goals', player_id: 912, name: 'Private Name', group: 'Private group', mode: '1v1' },
    })).toMatchObject({ data: { block: 'player_goals' } })
    for (const block of ['private-player', '__proto__', 912, undefined]) {
      expect(window.pnballieAnalyticsBeforeSend?.('event', { url: '/app/stats_players', name: 'stats_block_viewed', data: { block } })).toBeNull()
    }
    expect(window.pnballieAnalyticsBeforeSend?.('event', { url: '/app/game', name: 'stats_block_viewed', data: { block: 'player_goals' } })).toBeNull()
  })

  it.each(['dnt', 'gpc', 'optout'])('also respects %s when block collection is already configured', async choice => {
    const { track } = await enable()
    if (choice === 'dnt') Object.defineProperty(navigator, 'doNotTrack', { value: '1', configurable: true })
    if (choice === 'gpc') Object.defineProperty(navigator, 'globalPrivacyControl', { value: true, configurable: true })
    if (choice === 'optout') localStorage.setItem('umami.disabled', '1')
    analytics.trackStatsBlockView('ranking')
    expect(track).not.toHaveBeenCalled()
    Reflect.deleteProperty(navigator, 'globalPrivacyControl')
  })
})
