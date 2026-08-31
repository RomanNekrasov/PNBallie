import { afterEach, describe, expect, it, vi } from 'vitest'
import { loadRuntimeConfig, parseRuntimeConfig } from './runtimeConfig'

const valid = {
  azureClientId: 'client',
  azureTenantId: 'tenant',
  azureScope: 'api://client/user',
}

afterEach(() => vi.unstubAllGlobals())

describe('runtime configuration', () => {
  it('accepts the documented contract', () => {
    expect(parseRuntimeConfig(valid)).toEqual(valid)
  })

  it.each([null, {}, { ...valid, azureScope: '' }])('rejects missing or invalid values', value => {
    expect(() => parseRuntimeConfig(value)).toThrow('Ongeldige runtimeconfiguratie')
  })

  it('loads config without using a browser cache', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(valid) })
    vi.stubGlobal('fetch', fetchMock)
    await expect(loadRuntimeConfig()).resolves.toEqual(valid)
    expect(fetchMock).toHaveBeenCalledWith('/config.json', { cache: 'no-store' })
  })

  it('rejects an unavailable config endpoint', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
    await expect(loadRuntimeConfig()).rejects.toThrow('Runtimeconfiguratie kon niet worden geladen')
  })
})
