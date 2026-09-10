import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useMatch } from './useMatch'
import { api } from './useApi'
import { trackEvent } from '../analytics'

vi.mock('./useApi', () => ({ api: vi.fn() }))
vi.mock('../analytics', () => ({ trackEvent: vi.fn() }))
beforeEach(() => vi.clearAllMocks())

describe('successful match analytics', () => {
  it('emits only the formation after the API saved a match, without scores or player identifiers', async () => {
    const game = useMatch()
    game.setPlayer('orange_front', 198)
    game.setPlayer('blue_back', 299)
    game.orangeScore.value = 10
    game.blueScore.value = 7
    vi.mocked(api).mockResolvedValueOnce({ id: 88, players: [], orange_score: 10, blue_score: 7 })
    await game.submitMatch()
    expect(trackEvent).toHaveBeenCalledExactlyOnceWith('match_saved', { mode: '1v1' })
  })

  it('does not count a failed save as a successful action', async () => {
    vi.mocked(api).mockRejectedValueOnce(new Error('Unavailable'))
    await expect(useMatch().submitMatch()).rejects.toThrow('Unavailable')
    expect(trackEvent).not.toHaveBeenCalled()
  })
})

describe('rotatePlayers', () => {
  it('does not remove players when both 1v1 selections are on the same side', () => {
    const { selectedPlayers, setPlayer, rotatePlayers } = useMatch()
    setPlayer('orange_front', 1)
    setPlayer('orange_back', 2)

    rotatePlayers()

    expect(selectedPlayers.value).toEqual({
      orange_front: 1,
      orange_back: 2,
      blue_front: null,
      blue_back: null,
    })
  })

  it('moves every 2v2 player one position clockwise', () => {
    const { selectedPlayers, setPlayer, rotatePlayers } = useMatch()
    setPlayer('blue_back', 1)
    setPlayer('orange_front', 2)
    setPlayer('orange_back', 3)
    setPlayer('blue_front', 4)

    rotatePlayers()

    expect(selectedPlayers.value).toEqual({
      blue_back: 4,
      orange_front: 1,
      orange_back: 2,
      blue_front: 3,
    })
  })
})
