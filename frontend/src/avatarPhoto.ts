const formats: Record<string, string> = {
  jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp',
  heic: 'image/heic', heif: 'image/heif',
}
const types = new Set([...Object.values(formats), 'image/heic-sequence', 'image/heif-sequence'])

export function photoMime(file: File): string | null {
  const type = file.type.toLowerCase()
  if (types.has(type)) return type
  if (type === 'image/jpg') return 'image/jpeg'
  // Safari/File providers sometimes omit the MIME type. The API still checks
  // the actual encoded format; an extension never replaces server validation.
  if (!type || type === 'application/octet-stream') {
    return formats[file.name.split('.').pop()?.toLowerCase() ?? ''] ?? null
  }
  return null
}
