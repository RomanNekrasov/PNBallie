import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../auth', () => ({ getAccessToken: vi.fn().mockResolvedValue('access-token') }))

import { api } from './useApi'

afterEach(() => vi.unstubAllGlobals())

describe('api', () => {
  it('sends the bearer token', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve({ ok: true }) })
    vi.stubGlobal('fetch', fetchMock)
    await api('/api/test')
    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer access-token')
  })
})
