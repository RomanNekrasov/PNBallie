import { afterEach, describe, expect, it, vi } from 'vitest'
import { authProviders, authUser, clearSession, csrfToken, currentGroup, initAuth, login, logout, safeReturnPath } from './auth'

afterEach(() => { vi.unstubAllGlobals(); clearSession(); localStorage.clear() })
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status })

describe('portable authentication', () => {
  it('starts without an account or Entra configuration', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(json({ local: true, registration_enabled: true, oidc: null }))
      .mockResolvedValueOnce(json({}, 401)))
    await initAuth()
    expect(authUser.value).toBeNull()
    expect(authProviders.value?.local).toBe(true)
  })
  it('restores cookie session and chooses only a group the user belongs to', async () => {
    localStorage.setItem('pnballie.group', '999')
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(json({ local: true, registration_enabled: true, oidc: null }))
      .mockResolvedValueOnce(json({ user: { id: 1, email: 'a@example.test', display_name: 'A' }, csrf_token: 'csrf' }))
      .mockResolvedValueOnce(json([{ id: 5, name: 'Five', role: 'member', player_id: 8 }])))
    await initAuth()
    expect(currentGroup.value?.id).toBe(5)
    expect(csrfToken.value).toBe('csrf')
  })
  it('login and logout keep credentials out of browser storage', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(json({ user: { id: 1, email: 'a@example.test', display_name: 'A' }, csrf_token: 'csrf' }))
      .mockResolvedValueOnce(json([]))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)
    await login('a@example.test', 'a secure password')
    expect(authUser.value?.id).toBe(1)
    expect(localStorage.length).toBe(0)
    await logout()
    expect(authUser.value).toBeNull()
    expect((fetchMock.mock.calls[2]?.[1].headers as Headers).get('X-CSRF-Token')).toBe('csrf')
  })
  it.each(['https://example.test', '//example.test', '/\\example.test', '/%2fexample.test', '/%5cexample.test', '/%0aexample.test', '/%', null, '/login'])('rejects unsafe or looping login return path %s', value => {
    expect(safeReturnPath(value)).toBe('/')
  })
  it('preserves an invitation after login', () => {
    expect(safeReturnPath('/join/code-example')).toBe('/join/code-example')
  })
})
