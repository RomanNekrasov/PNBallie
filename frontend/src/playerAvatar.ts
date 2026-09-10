const PLAYER_AVATARS: Record<string, string> = {
  roman: '/avatars/roman.png',
  ruben: '/avatars/ruben.png',
  kaz: '/avatars/kaz.png',
  brent: '/avatars/brent.png',
}

export function playerAvatar(name: string | null | undefined, customUrl?: string | null): string | null {
  if (customUrl?.startsWith('/api/avatars/players/')) return customUrl
  if (!name) return null
  return PLAYER_AVATARS[name.trim().toLocaleLowerCase('nl-NL')] ?? null
}

export function playerInitials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .map(part => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}
