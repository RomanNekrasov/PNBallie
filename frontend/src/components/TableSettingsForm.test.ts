import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { clearSession, currentGroup, groups, selectGroup } from '../auth'
import { api } from '../composables/useApi'
import { useTableSettings } from '../composables/useTableSettings'
import { defaultTableSettings, scoreSideAtTop } from '../tableSettings'
import TableSettingsForm from './TableSettingsForm.vue'

vi.mock('../composables/useApi', () => ({ api: vi.fn() }))
let wrapper: VueWrapper | undefined
beforeEach(() => {
  groups.value = [{ id: 1, name: 'Club A', role: 'admin', player_id: 1, table_settings: { ...defaultTableSettings } },
    { id: 2, name: 'Club B', role: 'admin', player_id: 2 }]
  selectGroup(1)
})
afterEach(() => { wrapper?.unmount(); clearSession(); vi.resetAllMocks() })

describe('group table configuration', () => {
  it('previews edits without changing the active table until saved', async () => {
    wrapper = mount(TableSettingsForm)
    const controls = wrapper.findAll('select')
    await controls[0]!.setValue('red')
    await controls[2]!.setValue('own_goal')
    expect(wrapper.get('.score-top').text()).toBe('Rood · 0')
    expect(wrapper.get('.table-preview').attributes('style')).toContain('--team-blue: #d54444')
    expect(currentGroup.value?.table_settings).toEqual(defaultTableSettings)
    const settings = { ...defaultTableSettings, blue_color: 'red', score_position: 'own_goal' }
    vi.mocked(api).mockResolvedValue({ ...groups.value[0], table_settings: settings })
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(api).toHaveBeenCalledWith('/api/groups/current/table', { method: 'PUT', body: JSON.stringify(settings) })
    expect(currentGroup.value?.table_settings).toEqual(settings)
    expect(wrapper.get('[role="status"]').text()).toContain('opgeslagen')
  })

  it('preserves the active configuration and draft after a failed save', async () => {
    wrapper = mount(TableSettingsForm)
    await wrapper.findAll('select')[0]!.setValue('white')
    vi.mocked(api).mockRejectedValue(new Error('Opslaan mislukt'))
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('Opslaan mislukt')
    expect(wrapper.get('.score-bottom').text()).toBe('Wit · 0')
    expect(currentGroup.value?.table_settings).toEqual(defaultTableSettings)
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  it('resets only the preview until explicitly saved', async () => {
    wrapper = mount(TableSettingsForm)
    await wrapper.findAll('select')[2]!.setValue('own_goal')
    await wrapper.get('button[type="button"]').trigger('click')
    expect(wrapper.get('.score-top').text()).toBe('Oranje · 0')
    expect(api).not.toHaveBeenCalled()
  })

  it('follows the selected group and keeps score side identifiers stable', () => {
    const state = useTableSettings()
    groups.value[0]!.table_settings = { ...defaultTableSettings, orange_color: 'yellow', blue_color: 'black', score_position: 'own_goal' }
    expect(state.teamName('orange')).toBe('Geel')
    expect(state.teamName('blue')).toBe('Zwart')
    expect(scoreSideAtTop(state.tableSettings.value)).toBe('blue')
    selectGroup(2)
    expect(state.teamName('orange')).toBe('Oranje')
    expect(scoreSideAtTop(state.tableSettings.value)).toBe('orange')
  })
})
