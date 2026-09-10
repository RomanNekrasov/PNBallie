// @vitest-environment node
/// <reference types="node" />
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'

const directories: string[] = []
afterEach(() => { directories.splice(0).forEach(path => rmSync(path, { recursive: true, force: true })) })
function render(overrides: Record<string, string> = {}) {
  const directory = mkdtempSync(join(tmpdir(), 'pnballie-analytics-'))
  directories.push(directory)
  execFileSync('/bin/sh', ['40-pnballie-analytics.sh'], {
    cwd: process.cwd(), stdio: 'pipe',
    env: { ...process.env, PNBALLIE_RUNTIME_DIR: directory, ANALYTICS_ENABLED: 'false', ANALYTICS_WEBSITE_ID: '',
      ANALYTICS_UPSTREAM: '', ANALYTICS_TRUSTED_PROXY_CIDRS: '', ANALYTICS_DNS_RESOLVER: '127.0.0.11', ...overrides },
  })
  return {
    config: JSON.parse(readFileSync(join(directory, 'pnballie-config.json'), 'utf8')),
    server: readFileSync(join(directory, 'pnballie-analytics-server.conf'), 'utf8'),
    http: readFileSync(join(directory, 'pnballie-analytics-http.conf'), 'utf8'),
    headers: readFileSync(join(directory, 'pnballie-analytics-proxy.conf'), 'utf8'),
  }
}
const enabled = {
  ANALYTICS_ENABLED: 'true', ANALYTICS_WEBSITE_ID: '03c9b13b-4507-517c-b008-c488152a163b',
  ANALYTICS_UPSTREAM: 'umami.analytics.svc.cluster.local:3000',
}

describe('read-only container analytics configuration', () => {
  it('starts disabled without requiring an upstream DNS name', () => {
    const output = render()
    expect(output.config.analytics).toEqual({ enabled: false, websiteId: '' })
    expect(output.server).not.toContain('proxy_pass')
  })

  it('publishes a non-secret UUID and resolves an unavailable upstream at request time', () => {
    const output = render(enabled)
    expect(output.config.analytics).toEqual({ enabled: true, websiteId: enabled.ANALYTICS_WEBSITE_ID })
    expect(output.server).toContain('proxy_pass $analytics_backend/api/send;')
    expect(output.server).toContain('resolver 127.0.0.11')
    expect(output.server).not.toContain('proxy_pass http://umami')
  })

  it('rejects config injection and untrusted all-network proxy ranges', () => {
    const output = render({ ...enabled, ANALYTICS_WEBSITE_ID: enabled.ANALYTICS_WEBSITE_ID + '\n"injected":"value' })
    expect(output.config.analytics.enabled).toBe(false)
    expect(output.server).not.toContain('injected')
    const proxy = render({ ...enabled, ANALYTICS_TRUSTED_PROXY_CIDRS: '0.0.0.0/0 10.42.0.7/32' })
    expect(proxy.server).not.toContain('set_real_ip_from 0.0.0.0/0')
    expect(proxy.server).toContain('set_real_ip_from 10.42.0.7/32')
  })

  it('does not forward cookies, bearer credentials, referrers or visitor-supplied geo headers', () => {
    const output = render(enabled)
    expect(output.http).toContain('default 0;')
    expect(output.http).toContain('default "";')
    for (const header of ['Cookie', 'Authorization', 'Referer', 'Forwarded', 'CF-Connecting-IP', 'CF-IPCountry']) {
      expect(output.headers).toContain(`proxy_set_header ${header} "";`)
    }
    expect(output.headers).toContain('proxy_set_header X-Forwarded-For $analytics_client_ip;')
    expect(output.headers).not.toMatch(/\$http_(x_forwarded_for|cf_connecting_ip)/)
  })
})
