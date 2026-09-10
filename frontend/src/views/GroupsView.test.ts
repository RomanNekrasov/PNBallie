import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { RouterView } from 'vue-router'
import { authProviders, authUser, clearSession, currentGroup, groups } from '../auth'
import router from '../router'

const { apiMock, loginMock, registerMock, refreshGroupsMock } = vi.hoisted(() => ({
  apiMock: vi.fn(), loginMock: vi.fn(), registerMock: vi.fn(), refreshGroupsMock: vi.fn(),
}))
vi.mock('../composables/useApi', () => ({ api: apiMock }))
vi.mock('../auth', async importOriginal => ({
  ...await importOriginal<typeof import('../auth')>(),
  login: loginMock, register: registerMock, refreshGroups: refreshGroupsMock,
}))
vi.mock('./GameView.vue', () => ({ default: { template: '<p>Scorebord</p>' } }))

let wrapper: VueWrapper | undefined
const joinedGroup = { id: 42, name: 'De kantinetoppers', role: 'member' as const, player_id: 23 }

beforeEach(async () => {
  clearSession()
  localStorage.clear()
  authProviders.value = {
    local: true, registration_enabled: true,
    oidc: { name: 'Eigen SSO', login_url: '/api/auth/oidc/login' },
  }
  const authenticate = async () => { authUser.value = { id: 1, email: 'ada@example.test', display_name: 'Ada' } }
  loginMock.mockImplementation(authenticate)
  registerMock.mockImplementation(authenticate)
  refreshGroupsMock.mockImplementation(async () => { groups.value = [joinedGroup] })
  apiMock.mockResolvedValue(joinedGroup)
  await router.push('/login')
  await router.isReady()
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  clearSession()
  localStorage.clear()
  vi.resetAllMocks()
})

describe('joining a group through an invitation', () => {
  it.each(['login', 'register'] as const)('preserves the invitation through %s and joins only on submission', async mode => {
    await router.push('/join/private-invitation-code')
    wrapper = mount(RouterView, { global: { plugins: [router] } })
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/login')
    expect(router.currentRoute.value.query.redirect).toBe('/join/private-invitation-code')
    expect(wrapper.text()).toContain('Je bent uitgenodigd voor een groep')
    expect(wrapper.get('a.secondary-button').attributes('href')).toBe('/api/auth/oidc/login?next=%2Fjoin%2Fprivate-invitation-code')

    if (mode === 'register') {
      await wrapper.findAll('.account-tabs button')[1]!.trigger('click')
      await wrapper.get('input[autocomplete="name"]').setValue('Ada')
    }
    await wrapper.get('input[type="email"]').setValue('ada@example.test')
    await wrapper.get('input[type="password"]').setValue('a-long-test-password')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mode === 'login' ? loginMock : registerMock).toHaveBeenCalledOnce()
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/join/private-invitation-code'))
    await flushPromises()
    const invitation = wrapper.get<HTMLInputElement>('input[placeholder="Code of link"]')
    expect(invitation.element.value).toBe('private-invitation-code')
    expect(apiMock).not.toHaveBeenCalled()
    await wrapper.findAll('form')[0]!.trigger('submit')
    await flushPromises()

    expect(apiMock).toHaveBeenCalledWith('/api/groups/join', {
      method: 'POST', body: JSON.stringify({ code: 'private-invitation-code' }),
    })
    expect(refreshGroupsMock).toHaveBeenCalledOnce()
    expect(currentGroup.value?.id).toBe(42)
    expect(router.currentRoute.value.path).toBe('/')
  })

  it('accepts a pasted invitation link and sends only its code', async () => {
    authUser.value = { id: 1, email: 'ada@example.test', display_name: 'Ada' }
    await router.push('/groups')
    wrapper = mount(RouterView, { global: { plugins: [router] } })
    await flushPromises()
    await wrapper.get('input[placeholder="Code of link"]').setValue('https://pool.example.test/join/link-code')
    await wrapper.findAll('form')[0]!.trigger('submit')
    await flushPromises()
    expect(apiMock).toHaveBeenCalledWith('/api/groups/join', {
      method: 'POST', body: JSON.stringify({ code: 'link-code' }),
    })
  })

  it('keeps an invalid invitation available to correct after an API error', async () => {
    authUser.value = { id: 1, email: 'ada@example.test', display_name: 'Ada' }
    await router.push('/join/expired-code')
    apiMock.mockRejectedValueOnce(new Error('Uitnodiging verlopen'))
    wrapper = mount(RouterView, { global: { plugins: [router] } })
    await flushPromises()
    await wrapper.findAll('form')[0]!.trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('Uitnodiging verlopen')
    expect(wrapper.get<HTMLInputElement>('input[placeholder="Code of link"]').element.value).toBe('expired-code')
    expect(currentGroup.value).toBeNull()
    expect(refreshGroupsMock).not.toHaveBeenCalled()
  })
})
