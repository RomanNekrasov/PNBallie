export interface RuntimeConfig {
  azureClientId: string
  azureTenantId: string
  azureScope: string
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

export function parseRuntimeConfig(value: unknown): RuntimeConfig {
  if (!value || typeof value !== 'object') {
    throw new Error('Ongeldige runtimeconfiguratie')
  }
  const config = value as Record<string, unknown>
  if (
    !isNonEmptyString(config.azureClientId)
    || !isNonEmptyString(config.azureTenantId)
    || !isNonEmptyString(config.azureScope)
  ) {
    throw new Error('Ongeldige runtimeconfiguratie')
  }
  return {
    azureClientId: config.azureClientId,
    azureTenantId: config.azureTenantId,
    azureScope: config.azureScope,
  }
}

export async function loadRuntimeConfig(): Promise<RuntimeConfig> {
  const response = await fetch('/config.json', { cache: 'no-store' })
  if (!response.ok) {
    throw new Error('Runtimeconfiguratie kon niet worden geladen')
  }
  return parseRuntimeConfig(await response.json())
}
