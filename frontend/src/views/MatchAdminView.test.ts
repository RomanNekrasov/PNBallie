import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import MatchAdminView from './MatchAdminView.vue'
import { authUser, clearSession, groups, selectGroup } from '../auth'
const { apiMock } = vi.hoisted(() => ({apiMock:vi.fn()}))
vi.mock('../composables/useApi', () => ({api:apiMock}))
const match={id:7,orange_score:10,blue_score:3,played_at:'2026-09-10T12:00:00Z',players:[{player_id:1,side:'orange',position:'solo'},{player_id:2,side:'blue',position:'solo'}]}
const players=[{id:1,name:'Ada',is_active:true},{id:2,name:'Bob',is_active:false}]
beforeEach(()=>{
  authUser.value={id:1,email:'admin@example.test',display_name:'Admin'}
  groups.value=[{id:1,name:'Pool',role:'admin',player_id:1}];selectGroup(1)
  apiMock.mockImplementation(async (path:string, options?:RequestInit)=>options ? undefined : path.startsWith('/api/matches')?[match]:players)
  HTMLElement.prototype.scrollIntoView=vi.fn()
})
afterEach(()=>{clearSession();vi.resetAllMocks()})
async function view(){
  const router=createRouter({history:createMemoryHistory(),routes:[{path:'/admin/matches',component:MatchAdminView},{path:'/stats',component:{template:'<p>Stats</p>'}}]})
  await router.push('/admin/matches');await router.isReady()
  const wrapper=mount(MatchAdminView,{global:{plugins:[router]}});await flushPromises();return wrapper
}
it('does not delete until the explicit confirmation and sends the observed version',async()=>{
  const wrapper=await view()
  await wrapper.findAll('button').find(b=>b.text()==='Verwijderen')!.trigger('click');await flushPromises()
  expect(apiMock.mock.calls.some(([,o])=>o?.method==='DELETE')).toBe(false)
  expect(wrapper.get('[aria-label="Verwijderen bevestigen"]').text()).toContain('Ada 10–3 Bob')
  await wrapper.findAll('button').find(b=>b.text()==='Definitief verwijderen')!.trigger('click');await flushPromises()
  const call=apiMock.mock.calls.find(([,o])=>o?.method==='DELETE')!
  expect(call[0]).toBe('/api/matches/7');expect(JSON.parse(call[1].body)).toEqual(match)
  wrapper.unmount()
})
it('edits a score while preserving the exact original instant and inactive participant',async()=>{
  const wrapper=await view()
  await wrapper.findAll('button').find(b=>b.text()==='Wijzigen')!.trigger('click');await flushPromises()
  expect(wrapper.text()).toContain('Bob (inactief)')
  await wrapper.findAll('input[type=number]')[1]!.setValue('4')
  await wrapper.get('form').trigger('submit');await flushPromises()
  const body=JSON.parse(apiMock.mock.calls.find(([,o])=>o?.method==='PUT')![1].body)
  expect(body.blue_score).toBe(4);expect(body.played_at).toBe(match.played_at);expect(body.expected).toEqual(match)
  wrapper.unmount()
})
it('keeps a conflict visible and reloads instead of retrying a mutation',async()=>{
  const wrapper=await view()
  await wrapper.findAll('button').find(b=>b.text()==='Wijzigen')!.trigger('click');await flushPromises()
  apiMock.mockImplementationOnce(()=>Promise.reject(new Error('Deze wedstrijd is intussen gewijzigd.')))
  await wrapper.get('form').trigger('submit');await flushPromises()
  expect(wrapper.get('[role=alert]').text()).toContain('intussen gewijzigd')
  expect(wrapper.find('form').exists()).toBe(true)
  expect(apiMock.mock.calls.filter(([,o])=>o?.method==='PUT')).toHaveLength(1)
  wrapper.unmount()
})

it('shows the original recorder and an explicit unknown for historical matches',async()=>{
  apiMock.mockImplementation(async(path:string)=>path.startsWith('/api/matches') ? [{...match, recorded_by:{user_id:8,name:'Scorekeeper'}},{...match,id:9,recorded_by:null}] : players)
  const wrapper=await view()
  expect(wrapper.text()).toContain('Ingevoerd door Scorekeeper')
  expect(wrapper.text()).toContain('Ingevoerd door Onbekend')
  wrapper.unmount()
})
