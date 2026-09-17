/** Vite fingerprints the selected assets so deployments cannot serve stale icons. */
const images = import.meta.glob<string>('./assets/game3d/*.webp', {
  eager: true,
  query: '?url',
  import: 'default',
})

export function gameAssetUrl(key: string): string | undefined {
  return images[`./assets/game3d/${key}.webp`]
}
