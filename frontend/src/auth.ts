import { computed, ref } from 'vue'

export interface AuthUser {
  id: number
  email: string
  display_name: string
  has_password?: boolean
}
export interface Group {
  id: number
  name: string
  role: 'admin' | 'member'
  player_id: number | null
}
export interface AuthProviders {
  local: boolean
  registration_enabled: boolean
  oidc: { name: string; login_url: string } | null
}
interface AuthSession {
  user: AuthUser
  csrf_token: string
}

const GROUP_STORAGE_KEY = 'pnballie.group'
export const authUser = ref<AuthUser | null>(null)
export const groups = ref<Group[]>([])
export const csrfToken = ref<string | null>(null)
const selectedGroupId = ref<number | null>(null)
export const currentGroup = computed(() => groups.value.find(group => group.id === selectedGroupId.value) ?? null)
export const isGroupAdmin = computed(() => currentGroup.value?.role === 'admin')
export const authProviders = ref<AuthProviders | null>(null)

const API_MESSAGES: Record<string, string> = {
  'Invalid e-mail address or password': 'Het e-mailadres of wachtwoord klopt niet.',
  'This e-mail address is already registered': 'Er bestaat al een account met dit e-mailadres.',
  'Registration is disabled': 'Nieuwe accounts maken is op dit moment uitgeschakeld.',
  'Current password is incorrect': 'Je huidige wachtwoord klopt niet.',
  'Too many attempts; please try again later': 'Te veel pogingen. Probeer het later opnieuw.',
  'Invitation is invalid or expired': 'Deze uitnodiging is ongeldig of verlopen.',
  'Invitation has reached its usage limit': 'Deze uitnodiging is al volledig gebruikt.',
  'Please try joining the group again': 'Lid worden is nog niet gelukt. Probeer het opnieuw.',
  'Group not found': 'Deze groep is niet beschikbaar of je bent geen lid meer.',
  'Group administrator access is required': 'Alleen een groepsbeheerder kan dit doen.',
  'A group must keep at least one administrator': 'De groep moet minstens één beheerder houden.',
  'Player name or profile link already exists in this group': 'Deze spelersnaam of profielkoppeling bestaat al in je groep.',
  'No player profile is linked; ask your group administrator': 'Vraag je groepsbeheerder om je account aan een speler te koppelen.',
  'The linked user must be a member of this group': 'Het account moet lid zijn van deze groep.',
  'This member already has match history on another profile; keep that profile linked': 'Dit lid heeft al wedstrijden op een ander profiel. Behoud die koppeling.',
  'CSRF token is missing or invalid': 'Je sessie is niet meer actueel. Vernieuw de pagina en probeer het opnieuw.',
}

export function clearSession(): void {
  authUser.value = null
  csrfToken.value = null
  groups.value = []
  selectedGroupId.value = null
}

export async function responseError(response: Response): Promise<string> {
  const body = await response.json().catch(() => ({}))
  if (typeof body.detail === 'string') return API_MESSAGES[body.detail] ?? body.detail
  if (Array.isArray(body.detail)) return 'Controleer de ingevulde gegevens.'
  return `De aanvraag is mislukt (${response.status}). Probeer het opnieuw.`
}

async function authRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  if (csrfToken.value) headers.set('X-CSRF-Token', csrfToken.value)
  const response = await fetch(`/api/auth/${path}`, { ...options, headers, credentials: 'same-origin', cache: 'no-store' })
  if (!response.ok) throw new Error(await responseError(response))
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function refreshGroups(): Promise<void> {
  if (!authUser.value) return
  const response = await fetch('/api/groups', { credentials: 'same-origin', cache: 'no-store' })
  if (response.status === 401) {
    clearSession()
    throw new Error('Je sessie is verlopen. Log opnieuw in.')
  }
  if (!response.ok) throw new Error(await responseError(response))
  groups.value = await response.json() as Group[]
  let saved: number | null = selectedGroupId.value
  try { saved ??= Number(localStorage.getItem(GROUP_STORAGE_KEY)) || null } catch { /* storage may be disabled */ }
  selectedGroupId.value = groups.value.find(group => group.id === saved)?.id ?? groups.value[0]?.id ?? null
}

export function selectGroup(groupId: number): void {
  if (!groups.value.some(group => group.id === groupId)) throw new Error('Je bent geen lid van deze groep.')
  selectedGroupId.value = groupId
  try { localStorage.setItem(GROUP_STORAGE_KEY, String(groupId)) } catch { /* selection still works in memory */ }
}

export async function initAuth(): Promise<void> {
  authProviders.value = await authRequest<AuthProviders>('providers')
  const response = await fetch('/api/auth/me', { credentials: 'same-origin', cache: 'no-store' })
  if (response.status === 401) {
    clearSession()
    return
  }
  if (!response.ok) throw new Error(await responseError(response))
  const session = await response.json() as AuthSession
  authUser.value = session.user
  csrfToken.value = session.csrf_token
  await refreshGroups()
}

export async function login(email: string, password: string): Promise<void> {
  const session = await authRequest<AuthSession>('login', { method: 'POST', body: JSON.stringify({ email, password }) })
  authUser.value = session.user
  csrfToken.value = session.csrf_token
  await refreshGroups()
}

export async function register(email: string, password: string, displayName: string): Promise<void> {
  const session = await authRequest<AuthSession>('register', {
    method: 'POST', body: JSON.stringify({ email, password, display_name: displayName }),
  })
  authUser.value = session.user
  csrfToken.value = session.csrf_token
  await refreshGroups()
}

export async function logout(): Promise<void> {
  await authRequest<void>('logout', { method: 'POST' })
  clearSession()
  try { localStorage.removeItem(GROUP_STORAGE_KEY) } catch { /* no stored selection */ }
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  const session = await authRequest<AuthSession>('password', {
    method: 'POST', body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
  authUser.value = session.user
  csrfToken.value = session.csrf_token
}

export function safeReturnPath(value: unknown): string {
  if (typeof value !== 'string' || value.length > 500) return '/'
  try {
    const decoded = decodeURIComponent(value)
    if (!decoded.startsWith('/') || decoded.startsWith('//') || decoded.includes('\\')
      || Array.from(decoded).some(char => char.charCodeAt(0) < 32) || decoded.startsWith('/login')) return '/'
    return value
  } catch { return '/' }
}
