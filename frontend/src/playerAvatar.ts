const PLAYER_AVATARS: Record<string, string> = {
  roman: '/avatars/roman.png',
  ruben: '/avatars/ruben.png',
  kaz: '/avatars/kaz.png',
  brent: '/avatars/brent.png',
}

export function playerAvatar(name: string | null | undefined): string | null {
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
