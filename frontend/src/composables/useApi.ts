import { clearSession, csrfToken, currentGroup, responseError } from '../auth'

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (!path.startsWith('/api/')) throw new Error('Alleen lokale API-aanvragen zijn toegestaan.')
  const groupId = currentGroup.value?.id
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (groupId !== undefined) headers.set('X-Group-ID', String(groupId))
  const method = (options.method ?? 'GET').toUpperCase()
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfToken.value) {
    headers.set('X-CSRF-Token', csrfToken.value)
  }
  // Metadata/status reads must eventually settle so callers can resume polling.
  // Mutations retain their caller's signal and are never retried automatically.
  const controller = ['GET', 'HEAD'].includes(method) ? new AbortController() : null
  let timedOut = false
  const abortFromCaller = () => controller?.abort(options.signal?.reason)
  if (options.signal?.aborted) abortFromCaller()
  else if (controller) options.signal?.addEventListener('abort', abortFromCaller, { once: true })
  const timeout = controller ? setTimeout(() => { timedOut = true; controller.abort() }, 30_000) : undefined
  try {
    const response = await fetch(path, {
      ...options, headers, credentials: 'same-origin', cache: 'no-store',
      ...(controller ? { signal: controller.signal } : {}),
    })
    if (response.status === 401) {
      clearSession()
      throw new Error('Je sessie is verlopen. Log opnieuw in.')
    }
    if (!response.ok) throw new Error(await responseError(response))
    if (groupId !== currentGroup.value?.id) throw new Error('De actieve groep is gewijzigd. Probeer het opnieuw.')
    if (response.status === 204 || method === 'HEAD') return undefined as T
    return await response.json() as T
  } catch (cause) {
    if (timedOut) throw Object.assign(new Error('Gegevens ophalen duurt te lang. Probeer het opnieuw.'), { cause })
    throw cause
  } finally {
    clearTimeout(timeout)
    if (controller) options.signal?.removeEventListener('abort', abortFromCaller)
  }
}
