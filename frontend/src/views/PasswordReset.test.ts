import { mount, flushPromises } from '@vue/test-utils'
import { afterEach, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import ResetPasswordView from './ResetPasswordView.vue'
import ForgotPasswordView from './ForgotPasswordView.vue'
import LoginView from './LoginView.vue'
import { authProviders, authUser, clearSession } from '../auth'

const token = 'x'.repeat(43)
afterEach(() => { clearSession(); authProviders.value = null; vi.unstubAllGlobals() })
async function setup(path: string) {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/login', component: LoginView },
    { path: '/forgot-password', component: ForgotPasswordView },
    { path: '/reset-password', component: ResetPasswordView },
  ] })
  await router.push(path); await router.isReady()
  return router
}
it('strips the token, requires matching passwords and only resets on explicit submit', async () => {
  const router = await setup(`/reset-password#token=${token}`)
  authUser.value = { id: 1, email: 'a@example.test', display_name: 'A' }
  const fetchMock = vi.fn().mockResolvedValue(new Response(null, {status: 204}))
  vi.stubGlobal('fetch', fetchMock)
  const wrapper = mount(ResetPasswordView, { global: { plugins: [router] } })
  await flushPromises()
  expect(router.currentRoute.value.hash).toBe('')
  expect(fetchMock).not.toHaveBeenCalled()
  const inputs = wrapper.findAll('input')
  await inputs[0]!.setValue('a-new-long-password')
  await inputs[1]!.setValue('a-different-password')
  await wrapper.get('form').trigger('submit')
  expect(wrapper.get('[role=alert]').text()).toContain('niet gelijk')
  expect(fetchMock).not.toHaveBeenCalled()
  await inputs[1]!.setValue('a-new-long-password')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(JSON.parse(fetchMock.mock.calls[0]![1].body)).toEqual({token, new_password:'a-new-long-password'})
  expect(wrapper.get('[role=status]').text()).toContain('Log opnieuw in')
  expect(authUser.value).toBeNull()
  expect(wrapper.findAll('input')).toHaveLength(0)
  wrapper.unmount()
})
it('shows invalid-link guidance without making a request', async () => {
  const router = await setup('/reset-password#token=invalid')
  const fetchMock = vi.fn(); vi.stubGlobal('fetch', fetchMock)
  const wrapper = mount(ResetPasswordView, { global: { plugins: [router] } })
  await flushPromises()
  expect(wrapper.text()).toContain('Open de herstellink')
  expect(fetchMock).not.toHaveBeenCalled()
  expect(router.currentRoute.value.hash).toBe('')
  wrapper.unmount()
})
it('requests recovery and shows the neutral server response', async () => {
  const router = await setup('/forgot-password')
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ message:'Als dit adres bij een account hoort, ontvang je een herstellink.' }), {status:202}))
  vi.stubGlobal('fetch', fetchMock)
  const wrapper = mount(ForgotPasswordView, { global: { plugins: [router] } })
  await wrapper.get('input').setValue('a@example.test')
  await wrapper.get('form').trigger('submit'); await flushPromises()
  expect(fetchMock.mock.calls[0]![0]).toBe('/api/auth/password/forgot')
  expect(wrapper.get('[role=status]').text()).toContain('Als dit adres')
  expect(wrapper.find('form').exists()).toBe(false)
  wrapper.unmount()
})
it('offers recovery only when configured and renders the shared table', async () => {
  const router = await setup('/login')
  authProviders.value = {local:true, registration_enabled:true, oidc:null, password_reset_enabled:true}
  const wrapper = mount(LoginView, { global: { plugins: [router] } })
  expect(wrapper.get('a[href="/forgot-password"]').text()).toBe('Wachtwoord vergeten?')
  expect(wrapper.find('.auth-table svg').exists()).toBe(true)
  expect(wrapper.find('.login-art').exists()).toBe(false)
  authProviders.value.password_reset_enabled = false
  await flushPromises()
  expect(wrapper.find('a[href="/forgot-password"]').exists()).toBe(false)
  wrapper.unmount()
})
