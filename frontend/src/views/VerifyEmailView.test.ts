import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import VerifyEmailView from './VerifyEmailView.vue'
import { authUser, clearSession, verificationSent } from '../auth'

const token = 'x'.repeat(43)
afterEach(() => { clearSession(); vi.unstubAllGlobals() })

it('removes the fragment and only confirms on an explicit click', async () => {
  authUser.value = { id: 1, email: 'a@example.test', display_name: 'A', verification_required: true }
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/verify-email', component: VerifyEmailView }] })
  await router.push(`/verify-email#token=${token}`)
  await router.isReady()
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({detail: 'Deze link is verlopen.'}), {status:400}))
  vi.stubGlobal('fetch', fetchMock)
  const wrapper = mount(VerifyEmailView, { global: { plugins: [router] } })
  await flushPromises()
  expect(router.currentRoute.value.hash).toBe('')
  expect(fetchMock).not.toHaveBeenCalled()
  await wrapper.findAll('button').find(b => b.text() === 'E-mailadres bevestigen')!.trigger('click')
  await flushPromises()
  expect(fetchMock).toHaveBeenCalledTimes(1)
  expect(fetchMock.mock.calls[0]![0]).toBe('/api/auth/email/confirm')
  expect(wrapper.get('[role=alert]').text()).toBe('Deze link is verlopen.')
  wrapper.unmount()
})

it('shows delivery feedback and a resend cooldown without sending automatically', async () => {
  authUser.value = { id: 1, email: 'a@example.test', display_name: 'A', verification_required: true }
  verificationSent.value = true
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/verify-email', component: VerifyEmailView }] })
  await router.push('/verify-email'); await router.isReady()
  const fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock)
  const wrapper = mount(VerifyEmailView, { global: { plugins: [router] } })
  expect(wrapper.text()).toContain('Open de link in je mail')
  expect(wrapper.findAll('button')[0]!.attributes('disabled')).toBeDefined()
  expect(fetchMock).not.toHaveBeenCalled()
  wrapper.unmount()
})
