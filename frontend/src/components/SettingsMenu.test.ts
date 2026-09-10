import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { authUser, clearSession, groups, selectGroup } from '../auth'
import SettingsMenu from './SettingsMenu.vue'

const { logoutMock } = vi.hoisted(() => ({ logoutMock: vi.fn() }))
vi.mock('../auth', async importOriginal => ({
  ...await importOriginal<typeof import('../auth')>(), logout: logoutMock,
}))

let wrapper: VueWrapper | undefined
let router: Router

beforeEach(async () => {
  clearSession()
  authUser.value = { id: 1, email: 'player@example.test', display_name: 'Player' }
  groups.value = [{ id: 2, name: 'De kantinetoppers', role: 'admin', player_id: 3 }]
  selectGroup(2)
  logoutMock.mockResolvedValue(undefined)
  router = createRouter({
    history: createMemoryHistory(),
    routes: ['/stats', '/profile', '/groups', '/admin', '/login'].map(path => ({ path, component: { template: '<main>Page</main>' } })),
  })
  await router.push('/stats')
  await router.isReady()
  wrapper = mount(SettingsMenu, { attachTo: document.body, global: { plugins: [router] } })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  clearSession()
  localStorage.clear()
  vi.resetAllMocks()
})

describe('compact account menu', () => {
  it('starts collapsed and shows the group plus available account destinations on demand', async () => {
    expect(wrapper!.find('nav').exists()).toBe(false)
    expect(wrapper!.get('.settings-toggle').attributes('aria-expanded')).toBe('false')
    await wrapper!.get('.settings-toggle').trigger('click')
    expect(wrapper!.get('.settings-toggle').attributes('aria-expanded')).toBe('true')
    expect(wrapper!.get('.settings-group').text()).toContain('De kantinetoppers')
    expect(wrapper!.findAll('nav a').map(link => link.attributes('href'))).toEqual(['/profile', '/groups', '/admin'])
  })

  it('hides group administration from members and group-dependent destinations without a selected group', async () => {
    groups.value = [{ id: 2, name: 'Pool', role: 'member', player_id: 3 }]
    await wrapper!.get('.settings-toggle').trigger('click')
    expect(wrapper!.find('a[href="/admin"]').exists()).toBe(false)
    groups.value = []
    await flushPromises()
    expect(wrapper!.find('a[href="/profile"]').exists()).toBe(false)
    expect(wrapper!.find('a[href="/groups"]').exists()).toBe(true)
  })

  it('supports keyboard opening, Escape and returning focus to the settings button', async () => {
    const button = wrapper!.get<HTMLButtonElement>('.settings-toggle')
    button.element.focus()
    await button.trigger('keydown', { key: 'ArrowDown' })
    expect(document.activeElement).toBe(wrapper!.get('nav a').element)
    await wrapper!.get('nav a').trigger('keydown', { key: 'Escape' })
    expect(wrapper!.find('nav').exists()).toBe(false)
    expect(document.activeElement).toBe(button.element)
  })

  it('closes when clicking outside or navigating to a destination', async () => {
    await wrapper!.get('.settings-toggle').trigger('click')
    document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))
    await flushPromises()
    expect(wrapper!.find('nav').exists()).toBe(false)
    await wrapper!.get('.settings-toggle').trigger('click')
    await wrapper!.get('a[href="/profile"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/profile')
    expect(wrapper!.find('nav').exists()).toBe(false)
  })

  it('logs out through the session API and returns to the login screen', async () => {
    await wrapper!.get('.settings-toggle').trigger('click')
    await wrapper!.get('.settings-logout').trigger('click')
    await flushPromises()
    expect(logoutMock).toHaveBeenCalledOnce()
    expect(router.currentRoute.value.path).toBe('/login')
    expect(wrapper!.find('nav').exists()).toBe(false)
  })

  it('keeps a failed logout visible and allows retrying', async () => {
    logoutMock.mockRejectedValueOnce(new Error('De verbinding is verbroken.'))
    await wrapper!.get('.settings-toggle').trigger('click')
    await wrapper!.get('.settings-logout').trigger('click')
    await flushPromises()
    expect(wrapper!.get('[role="alert"]').text()).toBe('De verbinding is verbroken.')
    expect(router.currentRoute.value.path).toBe('/stats')
    expect(wrapper!.get('.settings-logout').attributes('disabled')).toBeUndefined()
  })
})
