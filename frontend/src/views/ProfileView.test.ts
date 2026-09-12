import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import ProfileView from './ProfileView.vue'

const { apiMock, fetchStatsMock, analyticsMock } = vi.hoisted(() => ({ apiMock: vi.fn(), fetchStatsMock: vi.fn(), analyticsMock: vi.fn() }))
vi.mock('../analytics', () => ({ trackEvent: analyticsMock, analyticsEnabled: ref(false) }))
vi.mock('../composables/useApi', () => ({ api: apiMock }))
vi.mock('../composables/useStats', () => ({ useStats: () => ({ stats: ref({ players: [] }), fetchStats: fetchStatsMock }) }))
vi.mock('../auth', () => ({
  authUser: ref({ id: 1, email: 'ada@example.test', display_name: 'Ada', has_password: false }),
  currentGroup: ref({ id: 7, name: 'Onze pool', role: 'member', player_id: 12 }),
  changePassword: vi.fn(), refreshGroups: vi.fn(),
}))

type JobStatus = 'queued' | 'processing' | 'succeeded' | 'failed' | 'cancelled'
function job(status: JobStatus) {
  return { id: 'avatar-job', status, provider: 'local', created_at: new Date(Date.now() - 5 * 60_000).toISOString(), error: null as string | null, avatar_url: status === 'succeeded' ? '/api/avatars/players/12.png?v=new' : null }
}
let latest: ReturnType<typeof job> | null
let configuration: { local_available: boolean; openai_available: boolean; max_upload_bytes: number }
let wrapper: VueWrapper | undefined

beforeEach(() => {
  vi.useFakeTimers()
  latest = null
  configuration = { local_available: true, openai_available: true, max_upload_bytes: 8 * 1024 * 1024 }
  fetchStatsMock.mockResolvedValue(undefined)
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:selected-portrait')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  apiMock.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path === '/api/players/me') return { id: 12, group_id: 7, user_id: 1, name: 'Ada', is_active: true, created_at: '2026-01-01T00:00:00Z', avatar_url: null }
    if (path === '/api/avatars/config') return { ...configuration }
    if (path === '/api/avatars/me/latest') return latest ? { ...latest } : null
    if (path.startsWith('/api/avatars/me/jobs?')) return job('queued')
    if (path === '/api/avatars/jobs/avatar-job') return job(options?.method === 'DELETE' ? 'cancelled' : 'succeeded')
    throw new Error(`Unexpected test API call: ${path}`)
  })
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.restoreAllMocks()
  vi.resetAllMocks()
  vi.useRealTimers()
})

async function openProfile() {
  wrapper = mount(ProfileView, { global: { stubs: { SettingsMenu: true, RouterLink: { template: '<a><slot /></a>' } } } })
  await flushPromises()
  return wrapper
}

async function selectPhoto(view: VueWrapper, photo = new File(['portrait pixels'], 'portrait.png', { type: 'image/png' })) {
  const input = view.get<HTMLInputElement>('input[type="file"]')
  const transfer = new DataTransfer()
  transfer.items.add(photo)
  input.element.files = transfer.files
  await input.trigger('change')
  return photo
}

function uploadForm(view: VueWrapper) {
  return view.findAll('form').find(form => form.find('input[type="file"]').exists())!
}

function submissions() {
  return apiMock.mock.calls.filter(([path]) => path.startsWith('/api/avatars/me/jobs?'))
}

describe('profile avatar flow', () => {
  it('counts a newly observed outcome once without uploading job IDs or image URLs to analytics', async () => {
    latest = job('processing')
    await openProfile()
    expect(analyticsMock).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(analyticsMock).toHaveBeenCalledExactlyOnceWith('avatar_outcome', { provider: 'local', outcome: 'succeeded' })
    await vi.advanceTimersByTimeAsync(10000)
    expect(analyticsMock).toHaveBeenCalledTimes(1)
  })

  it('loads the profile and resumes its avatar job even while badge statistics remain pending', async () => {
    latest = job('processing')
    fetchStatsMock.mockImplementation(() => new Promise(() => {}))
    const view = await openProfile()
    expect(view.find('input[type="file"]').exists()).toBe(true)
    expect(view.text()).not.toContain('Je profiel wordt geladen')
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(apiMock).toHaveBeenCalledWith('/api/avatars/jobs/avatar-job')
    expect(view.text()).toContain('Je avatar is klaar!')
  })

  it('shows request age and a retry reason, then recovers from a failed status read', async () => {
    latest = { ...job('queued'), error: 'De dienst heeft tijdelijk geen capaciteit.' }
    const respond = apiMock.getMockImplementation()!
    let statusReads = 0
    apiMock.mockImplementation((path: string, options?: RequestInit) => {
      if (path === '/api/avatars/jobs/avatar-job' && !options?.method && statusReads++ === 0) {
        return Promise.reject(new Error('Status ophalen duurt te lang.'))
      }
      return respond(path, options)
    })
    const view = await openProfile()
    expect(view.text()).toContain('5 minuten geleden aangevraagd')
    expect(view.text()).toContain('De dienst heeft tijdelijk geen capaciteit.')
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(view.get('[role="alert"]').text()).toContain('Status ophalen duurt te lang')
    expect(view.text()).toContain('In de wachtrij')
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(view.text()).toContain('Je avatar is klaar!')
    expect(view.find('[role="alert"]').exists()).toBe(false)
  })

  it('keeps the displayed age based on the original request while a long job remains active', async () => {
    latest = job('processing')
    const original = { ...latest }
    const respond = apiMock.getMockImplementation()!
    apiMock.mockImplementation((path: string, options?: RequestInit) =>
      path === '/api/avatars/jobs/avatar-job' ? Promise.resolve({ ...original }) : respond(path, options))
    const view = await openProfile()
    expect(view.text()).toContain('5 minuten geleden aangevraagd')
    await vi.advanceTimersByTimeAsync(60_000)
    await flushPromises()
    expect(view.text()).toContain('6 minuten geleden aangevraagd')
    expect(view.text()).toContain('Je avatar wordt gemaakt')
  })

  it('dates a previous failure, keeps its reason collapsed, and accepts a fresh photo only on submission', async () => {
    latest = { ...job('failed'), created_at: '2026-09-11T20:32:44', error: 'De afbeeldingsdienst is tijdelijk niet beschikbaar.' }
    const view = await openProfile()
    expect(view.get('.job-status strong').text()).toBe('Vorige aanvraag mislukt')
    const requested = view.get('time')
    expect(requested.attributes('datetime')).toBe('2026-09-11T20:32:44.000Z')
    expect(requested.text()).toBe(new Intl.DateTimeFormat('nl-NL', {
      weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    }).format(new Date('2026-09-11T20:32:44Z')))
    const details = view.get('details')
    expect(details.attributes('open')).toBeUndefined()
    expect(details.get('summary').text()).toBe('Details vorige aanvraag')
    expect(details.get('small').text()).toBe(latest.error)
    expect(view.find('[role="alert"]').exists()).toBe(false)
    expect(view.text()).toContain('Kies opnieuw een foto om een nieuwe aanvraag te starten.')
    expect(view.text()).not.toContain('Avatars maken is momenteel niet beschikbaar.')
    expect(view.get('input[type="file"]').attributes('disabled')).toBeUndefined()
    const calls = apiMock.mock.calls.length
    await vi.advanceTimersByTimeAsync(10000)
    expect(apiMock.mock.calls).toHaveLength(calls)
    expect(analyticsMock).not.toHaveBeenCalled()
    await selectPhoto(view)
    expect(submissions()).toHaveLength(0)
    expect(uploadForm(view).get('button[type="submit"]').attributes('disabled')).toBeUndefined()
    await uploadForm(view).trigger('submit')
    await flushPromises()
    expect(submissions()).toHaveLength(1)
    expect(view.get('.job-status strong').text()).toBe('In de wachtrij')
    expect(view.find('details').exists()).toBe(false)
    expect(view.find('time').exists()).toBe(false)
    expect(view.text()).not.toContain('Vorige aanvraag mislukt')
    expect(view.text()).not.toContain(latest.error)
    expect(view.get('input[type="file"]').attributes('disabled')).toBeDefined()
  })

  it('keeps a current upload error visible separately from the previous failed request', async () => {
    latest = { ...job('failed'), error: 'De afbeeldingsdienst is tijdelijk niet beschikbaar.' }
    const respond = apiMock.getMockImplementation()!
    apiMock.mockImplementation((path: string, options?: RequestInit) => path.startsWith('/api/avatars/me/jobs?')
      ? Promise.reject(new Error('De afbeeldingsdienst is nog niet ingesteld.')) : respond(path, options))
    const view = await openProfile()
    await selectPhoto(view)
    await uploadForm(view).trigger('submit')
    await flushPromises()
    expect(view.get('[role="alert"]').text()).toBe('De afbeeldingsdienst is nog niet ingesteld.')
    expect(view.get('.job-status strong').text()).toBe('Vorige aanvraag mislukt')
    expect(view.get('details small').text()).toBe(latest.error)
    expect(view.get('input[type="file"]').attributes('disabled')).toBeUndefined()
  })

  it('still shows unavailable configuration without suggesting an upload that cannot be made', async () => {
    latest = { ...job('failed'), error: 'De afbeeldingsdienst is tijdelijk niet beschikbaar.' }
    configuration.local_available = configuration.openai_available = false
    const view = await openProfile()
    expect(view.get('.job-status strong').text()).toBe('Vorige aanvraag mislukt')
    expect(view.text()).toContain('Avatars maken is momenteel niet beschikbaar.')
    expect(view.text()).not.toContain('Kies opnieuw een foto om een nieuwe aanvraag te starten.')
    expect(view.find('input[type="file"]').exists()).toBe(false)
    expect(submissions()).toHaveLength(0)
  })

  it('retains the selected File when clearing the native input and uploads only on submission', async () => {
    const view = await openProfile()
    const photo = await selectPhoto(view)
    expect(view.get<HTMLInputElement>('input[type="file"]').element.value).toBe('')
    expect(view.get('img[alt="Geselecteerde foto"]').attributes('src')).toBe('blob:selected-portrait')
    expect(submissions()).toHaveLength(0)
    expect(uploadForm(view).get('button[type="submit"]').attributes('disabled')).toBeUndefined()
    await uploadForm(view).trigger('submit')
    await flushPromises()
    expect(submissions()).toHaveLength(1)
    expect(submissions()[0]?.[0]).toBe('/api/avatars/me/jobs?provider=local&cloud_consent=false')
    const body = submissions()[0]?.[1]?.body as File
    expect(body).toBeInstanceOf(File)
    expect(body.name).toBe(photo.name)
    expect(await body.text()).toBe(await photo.text())
    expect(submissions()[0]?.[1]?.headers).toEqual({ 'Content-Type': 'image/png' })
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:selected-portrait')
    expect(view.find('img[alt="Geselecteerde foto"]').exists()).toBe(false)
    expect(view.text()).toContain('In de wachtrij')
  })

  it('requires explicit OpenAI consent even when OpenAI is the only configured provider', async () => {
    configuration.local_available = false
    const view = await openProfile()
    await selectPhoto(view)
    expect(view.get<HTMLSelectElement>('select').element.value).toBe('openai')
    expect(uploadForm(view).get('button[type="submit"]').attributes('disabled')).toBeDefined()
    // Submit directly as well: consent is checked by the handler, not just the button.
    await uploadForm(view).trigger('submit')
    expect(submissions()).toHaveLength(0)
    await view.get('input[type="checkbox"]').setValue(true)
    expect(submissions()).toHaveLength(0)
    await uploadForm(view).trigger('submit')
    await flushPromises()
    expect(submissions()[0]?.[0]).toBe('/api/avatars/me/jobs?provider=openai&cloud_consent=true')
  })

  it('clears cloud consent after switching provider', async () => {
    const view = await openProfile()
    await selectPhoto(view)
    await view.get('select').setValue('openai')
    await view.get('input[type="checkbox"]').setValue(true)
    await view.get('select').setValue('local')
    await view.get('select').setValue('openai')
    expect(view.get<HTMLInputElement>('input[type="checkbox"]').element.checked).toBe(false)
    await uploadForm(view).trigger('submit')
    expect(submissions()).toHaveLength(0)
  })

  it('resumes an existing job, polls to completion and displays the generated avatar', async () => {
    latest = job('processing')
    const view = await openProfile()
    expect(view.text()).toContain('Je avatar wordt gemaakt')
    expect(view.get('input[type="file"]').attributes('disabled')).toBeDefined()
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(apiMock).toHaveBeenCalledWith('/api/avatars/jobs/avatar-job')
    expect(view.text()).toContain('Je avatar is klaar!')
    expect(view.get('img[alt="Avatar van Ada"]').attributes('src')).toBe('/api/avatars/players/12.png?v=new')
    const count = apiMock.mock.calls.length
    await vi.advanceTimersByTimeAsync(15000)
    expect(apiMock.mock.calls).toHaveLength(count)
  })

  it('cancels a queued job and stops its scheduled polling', async () => {
    latest = job('queued')
    const view = await openProfile()
    const cancel = view.findAll('button').find(button => button.text() === 'Aanvraag annuleren')!
    await cancel.trigger('click')
    await flushPromises()
    expect(apiMock).toHaveBeenCalledWith('/api/avatars/jobs/avatar-job', { method: 'DELETE' })
    expect(view.text()).toContain('Aanvraag geannuleerd')
    expect(view.get('input[type="file"]').attributes('disabled')).toBeUndefined()
    const count = apiMock.mock.calls.length
    await vi.advanceTimersByTimeAsync(10000)
    expect(apiMock.mock.calls).toHaveLength(count)
  })

  it('keeps a completed cancellation when an older processing poll finishes late', async () => {
    latest = job('processing')
    let finishPoll!: (value: ReturnType<typeof job>) => void
    const pending = new Promise(resolve => { finishPoll = resolve })
    const respond = apiMock.getMockImplementation()!
    apiMock.mockImplementation((path: string, options?: RequestInit) =>
      path === '/api/avatars/jobs/avatar-job' && !options?.method ? pending : respond(path, options))
    const view = await openProfile()
    await vi.advanceTimersByTimeAsync(5000)
    const cancel = view.findAll('button').find(button => button.text() === 'Aanvraag annuleren')!
    await cancel.trigger('click')
    await flushPromises()
    expect(view.text()).toContain('Aanvraag geannuleerd')
    finishPoll(job('processing'))
    await flushPromises()
    expect(view.text()).toContain('Aanvraag geannuleerd')
    expect(view.get('input[type="file"]').attributes('disabled')).toBeUndefined()
    const count = apiMock.mock.calls.length
    await vi.advanceTimersByTimeAsync(10000)
    expect(apiMock.mock.calls).toHaveLength(count)
  })

  it('resumes polling after a failed cancellation so the active job can still finish', async () => {
    latest = job('processing')
    const respond = apiMock.getMockImplementation()!
    apiMock.mockImplementation((path: string, options?: RequestInit) => options?.method === 'DELETE'
      ? Promise.reject(new Error('Annuleren tijdelijk niet beschikbaar')) : respond(path, options))
    const view = await openProfile()
    const cancel = view.findAll('button').find(button => button.text() === 'Aanvraag annuleren')!
    await cancel.trigger('click')
    await flushPromises()
    expect(view.get('[role="alert"]').text()).toBe('Annuleren tijdelijk niet beschikbaar')
    expect(cancel.attributes('disabled')).toBeUndefined()
    await vi.advanceTimersByTimeAsync(5000)
    await flushPromises()
    expect(view.text()).toContain('Je avatar is klaar!')
  })

  it('stops polling and revokes the selected preview when leaving the profile', async () => {
    const view = await openProfile()
    await selectPhoto(view)
    view.unmount()
    wrapper = undefined
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:selected-portrait')
    const count = apiMock.mock.calls.length
    await vi.advanceTimersByTimeAsync(10000)
    expect(apiMock.mock.calls).toHaveLength(count)
  })
})
