import { getActiveAccount } from './auth'
import { api } from './composables/useApi'

function resolvePlayerName(): string | null {
  const account = getActiveAccount()
  const displayName = account?.name?.trim()
  if (displayName) {
    return displayName.split(/\s+/)[0] ?? null
  }
  const username = account?.username?.trim()
  if (!username) return null
  return username.split('@')[0]?.split(/[._-]/)[0] ?? null
}

export async function ensureLoggedInPlayerExists(): Promise<void> {
  const name = resolvePlayerName()
  if (!name) return

  try {
    await api('/api/players', {
      method: 'POST',
      body: JSON.stringify({ name }),
    })
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : ''
    const isAlreadyExists = message.includes('already exists') || message.includes('409')
    if (!isAlreadyExists) {
      throw error
    }
  }
}
