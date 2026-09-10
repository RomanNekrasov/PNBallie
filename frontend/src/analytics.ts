import { readonly, ref } from 'vue'

const screens = {
  game: 'Scorebord', stats_overview: 'Statistieken · overzicht', stats_ranking: 'Statistieken · ranglijst',
  stats_players: 'Statistieken · spelers', stats_matchups: 'Statistieken · onderling',
  profile: 'Eigen profiel', groups: 'Groepen', admin: 'Groepsbeheer', login: 'Inloggen',
} as const
export type AnalyticsScreen = keyof typeof screens
const eventFields = {
  match_saved: { mode: ['1v1', '2v2'] }, match_deleted: {},
  stats_filters_changed: { mode: ['all', '1v1', '2v2'], period: ['all', '30d', '50'] },
  comparison_selected: {}, profile_saved: {}, group_created: {}, group_joined: {},
  group_updated: {}, player_added: {}, player_updated: {}, member_updated: {}, member_removed: {},
  invite_created: {}, invite_revoked: {},
  avatar_queued: { provider: ['local', 'openai'] },
  avatar_outcome: { provider: ['local', 'openai'], outcome: ['succeeded', 'failed', 'cancelled'] },
  screen_visible_30s: {},
} as const
export type AnalyticsEvent = keyof typeof eventFields
type Payload = Record<string, unknown>
type Tracker = { track: (payload: Payload) => Promise<unknown> | undefined }
declare global {
  interface Window {
    umami?: Tracker
    pnballieAnalyticsBeforeSend?: (type: string, payload: Payload) => Payload | null
  }
}

const configured = ref(false)
export const analyticsEnabled = readonly(configured)
let websiteId = ''
let started = false
let ready = false
let accepting = false
let currentScreen: AnalyticsScreen | null = null
let visibleTimer: ReturnType<typeof setTimeout> | undefined
const pending: Payload[] = []
const hasOwn = (object: object, key: PropertyKey) => Object.prototype.hasOwnProperty.call(object, key)

function optedOut(): boolean {
  try {
    const browser = navigator as Navigator & { globalPrivacyControl?: boolean; msDoNotTrack?: string }
    return ['1', 'yes'].includes(String(browser.doNotTrack || browser.msDoNotTrack || (window as Window & { doNotTrack?: string }).doNotTrack))
      || browser.globalPrivacyControl === true || localStorage.getItem('umami.disabled') === '1'
  } catch { return true }
}

/** Runtime validation is deliberate: callers can never smuggle arbitrary event data. */
export function sanitizeAnalyticsPayload(type: string, input: Payload): Payload | null {
  if (type !== 'event' || !configured.value || optedOut()) return null
  const screen = Object.keys(screens).find(key => input.url === `/app/${key}`) as AnalyticsScreen | undefined
  if (!screen) return null
  const safe: Payload = {
    website: websiteId, hostname: window.location.hostname,
    url: `/app/${screen}`, title: screens[screen], referrer: '',
  }
  if (/^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$/i.test(navigator.language)) safe.language = navigator.language
  if (input.name !== undefined) {
    if (typeof input.name !== 'string' || !hasOwn(eventFields, input.name)) return null
    safe.name = input.name
    const fields = eventFields[input.name as AnalyticsEvent]
    const data = input.data && typeof input.data === 'object' ? input.data as Payload : {}
    const clean: Payload = {}
    for (const [key, allowed] of Object.entries(fields)) {
      if (!(allowed as readonly unknown[]).includes(data[key])) return null
      clean[key] = data[key]
    }
    if (Object.keys(clean).length) safe.data = clean
  }
  return safe
}

function deliver(payload: Payload) {
  const safe = sanitizeAnalyticsPayload('event', payload)
  if (!safe) return
  try { void Promise.resolve(window.umami?.track(safe)).catch(() => {}) } catch { /* analytics never blocks the app */ }
}
function emit(payload: Payload) {
  if (!accepting || optedOut()) return
  if (ready) deliver(payload)
  else if (pending.length < 20) pending.push(payload)
}
function scheduleEngagement() {
  clearTimeout(visibleTimer)
  if (!accepting || !currentScreen || document.visibilityState !== 'visible') return
  visibleTimer = setTimeout(() => trackEvent('screen_visible_30s'), 30_000)
}

export function trackScreen(screen: AnalyticsScreen) {
  if (!hasOwn(screens, screen) || currentScreen === screen) return
  currentScreen = screen
  emit({ url: `/app/${screen}` })
  scheduleEngagement()
}
export function trackEvent(name: AnalyticsEvent, data: Payload = {}) {
  if (!currentScreen || !hasOwn(eventFields, name)) return
  emit({ url: `/app/${currentScreen}`, name, data })
}

/** No authentication data, actual page URL, referrer or identities reach Umami. */
export async function initAnalytics(): Promise<void> {
  if (started) return
  started = true
  if (optedOut()) return
  accepting = true
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 3000)
  try {
    const response = await fetch('/config.json', { credentials: 'omit', cache: 'no-store', referrerPolicy: 'no-referrer', signal: controller.signal })
    if (!response.ok) throw new Error('Analytics configuration unavailable')
    const configuration = (await response.json())?.analytics
    if (configuration?.enabled !== true || typeof configuration.websiteId !== 'string'
      || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(configuration.websiteId)) {
      accepting = false
      pending.length = 0
      return
    }
    websiteId = configuration.websiteId
    configured.value = true
    window.pnballieAnalyticsBeforeSend = sanitizeAnalyticsPayload
    if (optedOut()) return
    const script = document.createElement('script')
    script.id = 'pnballie-analytics'
    script.src = '/analytics/script.js'
    script.async = true
    script.referrerPolicy = 'no-referrer'
    Object.assign(script.dataset, {
      websiteId, hostUrl: `${window.location.origin}/analytics`, autoTrack: 'false', autoPageview: 'false',
      doNotTrack: 'true', excludeSearch: 'true', excludeHash: 'true', performance: 'false',
      fetchCredentials: 'omit', beforeSend: 'pnballieAnalyticsBeforeSend',
    })
    script.onload = () => {
      ready = !!window.umami?.track
      if (ready) pending.splice(0).forEach(deliver)
      scheduleEngagement()
    }
    script.onerror = () => { accepting = false; pending.length = 0 }
    document.head.appendChild(script)
    document.addEventListener('visibilitychange', scheduleEngagement)
  } catch {
    accepting = false
    pending.length = 0
  } finally { clearTimeout(timeout) }
}

export function disposeAnalytics() {
  accepting = ready = false
  clearTimeout(visibleTimer)
  pending.length = 0
  document.removeEventListener('visibilitychange', scheduleEngagement)
  document.getElementById('pnballie-analytics')?.remove()
  window.pnballieAnalyticsBeforeSend = () => null
}
