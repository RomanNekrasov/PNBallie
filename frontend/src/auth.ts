import {
  InteractionRequiredAuthError,
  PublicClientApplication,
  type AccountInfo,
} from '@azure/msal-browser'
import { loadRuntimeConfig } from './runtimeConfig'

let msalInstance: PublicClientApplication | null = null
let scopes: string[] = []

function instance(): PublicClientApplication {
  if (!msalInstance) throw new Error('Authenticatie is nog niet geïnitialiseerd')
  return msalInstance
}

export async function initAuth(): Promise<void> {
  const config = await loadRuntimeConfig()
  msalInstance = new PublicClientApplication({
    auth: {
      clientId: config.azureClientId,
      authority: `https://login.microsoftonline.com/${config.azureTenantId}`,
      redirectUri: window.location.origin,
    },
  })
  scopes = [config.azureScope]
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
  return instance().getActiveAccount()
}

export async function login(): Promise<void> {
  await instance().loginRedirect({ scopes })
}

export async function logout(): Promise<void> {
  await instance().logoutRedirect()
}

export async function getAccessToken(): Promise<string | null> {
  const account = instance().getActiveAccount()
  if (!account) return null
  try {
    const response = await instance().acquireTokenSilent({ scopes, account })
    return response.accessToken
  } catch (error) {
    if (error instanceof InteractionRequiredAuthError) {
      await instance().acquireTokenRedirect({ scopes })
    }
    return null
  }
}
