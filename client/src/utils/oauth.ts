/**
 * OAuth utilities for Gmail and Outlook email connection
 */

import { apiClient } from '@/services/apiClient';

interface OAuthConfig {
  clientId: string;
  redirectUri: string;
  scope: string;
  authUrl: string;
}

/**
 * Get OAuth configuration from backend
 */
async function getOAuthConfig(provider: 'gmail' | 'outlook'): Promise<OAuthConfig> {
  try {
    const response = await apiClient.get<OAuthConfig>(`/email-service/email/oauth/config?provider=${provider}`);
    return response.data;
  } catch (error) {
    console.error('OAuth config request error:', error);
    throw error;
  }
}

// ── PKCE helpers (used for Outlook) ──────────────────────────────────────────

function generateRandomState(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return Array.from(array, b => b.toString(16).padStart(2, '0')).join('');
}

async function generatePKCE(): Promise<{ codeVerifier: string; codeChallenge: string }> {
  const codeVerifier = generateRandomState(); // 64-char hex string
  const encoder = new TextEncoder();
  const data = encoder.encode(codeVerifier);
  const digest = await crypto.subtle.digest('SHA-256', data);
  const codeChallenge = btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
  return { codeVerifier, codeChallenge };
}

/**
 * Initiate OAuth flow by redirecting to provider's consent screen.
 * Gmail uses plain state; Outlook uses PKCE (code_challenge).
 */
export async function initiateOAuth(provider: 'gmail' | 'outlook'): Promise<void> {
  try {
    const config = await getOAuthConfig(provider);

    const state = generateRandomState();
    sessionStorage.setItem('oauth_state', state);
    sessionStorage.setItem('oauth_provider', provider);

    const params = new URLSearchParams({
      client_id: config.clientId,
      redirect_uri: config.redirectUri,
      response_type: 'code',
      scope: config.scope,
      state,
    });

    if (provider === 'gmail') {
      // Gmail: standard OAuth with offline access
      params.set('access_type', 'offline');
      params.set('prompt', 'consent');
    } else {
      // Outlook: PKCE flow (recommended by Microsoft, no client_secret on frontend)
      const { codeVerifier, codeChallenge } = await generatePKCE();
      sessionStorage.setItem('oauth_code_verifier', codeVerifier);
      params.set('code_challenge', codeChallenge);
      params.set('code_challenge_method', 'S256');
      params.set('prompt', 'consent');
    }

    window.location.href = `${config.authUrl}?${params.toString()}`;
  } catch (error) {
    console.error('OAuth initiation failed:', error);
    throw error;
  }
}

/**
 * Handle OAuth callback and extract authorization code + optional PKCE verifier.
 */
export function handleOAuthCallback(): {
  code: string;
  provider: 'gmail' | 'outlook';
  codeVerifier?: string;
} | null {
  const params = new URLSearchParams(window.location.search);
  const code = params.get('code');
  const state = params.get('state');
  const error = params.get('error');

  if (error) {
    console.error('OAuth error:', error);
    return null;
  }

  const savedState = sessionStorage.getItem('oauth_state');
  if (!state || state !== savedState) {
    console.warn('OAuth state validation failed - callback may have already been processed');
    return null;
  }

  const provider = sessionStorage.getItem('oauth_provider') as 'gmail' | 'outlook' | null;
  if (!provider || !code) {
    console.warn('Missing OAuth provider or authorization code');
    return null;
  }

  const codeVerifier = sessionStorage.getItem('oauth_code_verifier') ?? undefined;

  // Clean up session storage
  sessionStorage.removeItem('oauth_state');
  sessionStorage.removeItem('oauth_provider');
  sessionStorage.removeItem('oauth_code_verifier');

  return { code, provider, codeVerifier };
}
