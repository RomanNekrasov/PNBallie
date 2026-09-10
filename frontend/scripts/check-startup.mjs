// Exercise the production bundle: lazy routes can deadlock with entry-module
// top-level await even when source-level component tests pass.
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright'
import { preview } from 'vite'

const server = await preview({
  root: fileURLToPath(new URL('..', import.meta.url)),
  preview: { host: '127.0.0.1', port: 0, strictPort: true },
})
let browser
try {
  const origin = `http://127.0.0.1:${server.httpServer.address().port}`
  browser = await chromium.launch({ headless: true })
  for (const path of ['/login', '/', '/profile', '/stats', '/join/private-invite-canary']) {
    const context = await browser.newContext()
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.route('**/api/auth/providers', route => route.fulfill({ json: {
      local: true, registration_enabled: true, oidc: null,
    } }))
    await page.route('**/api/auth/me', route => route.fulfill({ status: 401, json: {} }))
    await page.route('**/config.json', route => route.fulfill({ json: { analytics: {
      enabled: true, websiteId: '00000000-0000-4000-8000-000000000001',
    } } }))
    await page.route('**/analytics/script.js', route => route.fulfill({
      contentType: 'application/javascript',
      body: 'window.startupEvents=[];window.umami={track:payload=>{window.startupEvents.push(payload);return Promise.resolve()}}',
    }))
    await page.goto(origin + path, { waitUntil: 'domcontentloaded' })
    await page.getByLabel('E-mailadres').waitFor({ timeout: 5000 })
    await page.waitForFunction(() => window.startupEvents?.length > 0, undefined, { timeout: 5000 })
    const events = await page.evaluate(() => window.startupEvents)
    assert.deepEqual(events.map(event => event.url), ['/app/login'], path)
    assert.equal(JSON.stringify(events).includes('private-invite-canary'), false)
    assert.deepEqual(errors, [])
    await context.close()
  }
  console.log('Production bundle startup passed: five cold routes render login and emit only its safe screen.')
} finally {
  await browser?.close()
  await new Promise((resolve, reject) => server.httpServer.close(error => error ? reject(error) : resolve()))
}
