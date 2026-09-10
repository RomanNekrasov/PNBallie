import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { authUser, clearSession, csrfToken, groups, selectGroup } from '../auth'
import { api } from './useApi'

beforeEach(() => {
  clearSession()
  authUser.value = { id: 1, email: 'player@example.test', display_name: 'Player' }
  csrfToken.value = 'csrf-example'
  groups.value = [
    { id: 4, name: 'Group one', role: 'admin', player_id: 8 },
    { id: 5, name: 'Group two', role: 'member', player_id: 9 },
  ]
  selectGroup(4)
})
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); clearSession(); localStorage.clear() })
const ok = () => new Response(JSON.stringify({ ok: true }), { status: 200 })

describe('authenticated API', () => {
  it('aborts a hanging status read after 30 seconds and allows a subsequent read', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.fn().mockImplementationOnce((_path: string, options: RequestInit) => new Promise((_resolve, reject) => {
      options.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
    })).mockResolvedValueOnce(ok())
    vi.stubGlobal('fetch', fetchMock)
    const request = api('/api/avatars/jobs/example')
    const rejected = expect(request).rejects.toThrow('ophalen duurt te lang')
    await vi.advanceTimersByTimeAsync(30_000)
    await rejected
    expect(fetchMock).toHaveBeenCalledOnce()
    await expect(api('/api/avatars/jobs/example')).resolves.toEqual({ ok: true })
  })

  it('does not abort or retry a mutation because the status-read deadline elapsed', async () => {
    vi.useFakeTimers()
    let finish!: (response: Response) => void
    const fetchMock = vi.fn(() => new Promise<Response>(resolve => { finish = resolve }))
    vi.stubGlobal('fetch', fetchMock)
    const request = api('/api/avatars/me/jobs', { method: 'POST', body: 'image payload' })
    await vi.advanceTimersByTimeAsync(31_000)
    expect(fetchMock).toHaveBeenCalledOnce()
    expect((fetchMock.mock.calls[0] as unknown[] | undefined)?.[1]).not.toHaveProperty('signal')
    finish(ok())
    await expect(request).resolves.toEqual({ ok: true })
  })

  it('uses cookies, scoped group and CSRF on mutations without a bearer token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok())
    vi.stubGlobal('fetch', fetchMock)
    await api('/api/players', { method: 'POST', body: JSON.stringify({ name: 'New player' }) })
    const options = fetchMock.mock.calls[0]?.[1] as RequestInit
    const headers = options.headers as Headers
    expect(options.credentials).toBe('same-origin')
    expect(headers.get('X-Group-ID')).toBe('4')
    expect(headers.get('X-CSRF-Token')).toBe('csrf-example')
    expect(headers.has('Authorization')).toBe(false)
  })

  it('keeps a raw image upload and its content type intact', async () => {
    const fetchMock = vi.fn().mockResolvedValue(ok())
    vi.stubGlobal('fetch', fetchMock)
    const photo = new Blob(['example'], { type: 'image/png' })
    await api('/api/avatars/me/jobs', { method: 'POST', headers: { 'Content-Type': 'image/png' }, body: photo })
    const options = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect(options.body).toBe(photo)
    expect((options.headers as Headers).get('Content-Type')).toBe('image/png')
  })

  it('discards responses after the user changes group', async () => {
    let finish!: (response: Response) => void
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(resolve => { finish = resolve })))
    const request = api('/api/players')
    selectGroup(5)
    finish(ok())
    await expect(request).rejects.toThrow('actieve groep is gewijzigd')
  })

  it('clears private state when the session expires', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })))
    await expect(api('/api/players')).rejects.toThrow('sessie is verlopen')
    expect(authUser.value).toBeNull()
    expect(groups.value).toEqual([])
    expect(csrfToken.value).toBeNull()
  })

  it('returns validation errors as readable text', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ msg: 'bad value' }] }), { status: 422 })))
    await expect(api('/api/players')).rejects.toThrow('Controleer de ingevulde gegevens.')
  })

  it('never sends session or CSRF data to an external endpoint', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    await expect(api('https://example.test/api/steal')).rejects.toThrow('lokale API')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
