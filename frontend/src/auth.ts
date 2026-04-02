import {
  InteractionRequiredAuthError,
  PublicClientApplication,
  type AccountInfo,
} from '@azure/msal-browser'

const clientId = import.meta.env.VITE_AZURE_CLIENT_ID as string | undefined
const tenantId = import.meta.env.VITE_AZURE_TENANT_ID as string | undefined
const configuredScope = import.meta.env.VITE_AZURE_SCOPE as string | undefined

if (!clientId || !tenantId) {
  throw new Error('Missing MSAL env vars: VITE_AZURE_CLIENT_ID and VITE_AZURE_TENANT_ID are required')
}

const msalConfig = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri: window.location.origin,
  },
}

export const msalInstance = new PublicClientApplication(msalConfig)

const SCOPES = [configuredScope || 'User.Read']

export async function initAuth(): Promise<void> {
  await msalInstance.initialize()
  const result = await msalInstance.handleRedirectPromise()
  if (result?.account) {
    msalInstance.setActiveAccount(result.account)
  } else {
    const accounts = msalInstance.getAllAccounts()
    if (accounts.length > 0) {
      msalInstance.setActiveAccount(accounts[0] ?? null)
    }
  }
}

export function getActiveAccount(): AccountInfo | null {
  return msalInstance.getActiveAccount()
}

export async function login(): Promise<void> {
  await msalInstance.loginRedirect({ scopes: SCOPES })
}

export async function logout(): Promise<void> {
  await msalInstance.logoutRedirect()
}

export async function getAccessToken(): Promise<string | null> {
  const account = msalInstance.getActiveAccount()
  if (!account) return null
  try {
    const response = await msalInstance.acquireTokenSilent({ scopes: SCOPES, account })
    return response.accessToken
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) {
      await msalInstance.acquireTokenRedirect({ scopes: SCOPES })
    }
    return null
  }
}
