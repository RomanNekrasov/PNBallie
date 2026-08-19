import { describe, expect, it } from 'vitest'
import { useMatch } from './useMatch'

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
