/**
 * OAuth utilities for Gmail and Outlook email connection
 */

import { apiClient } from '@/services/apiClient';

const GOOGLE_OAUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth';
const MICROSOFT_OAUTH_URL = 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize';

// OAuth scopes
const GMAIL_SCOPES = [
  'https://www.googleapis.com/auth/gmail.send',
  'https://www.googleapis.com/auth/gmail.readonly',
  'https://www.googleapis.com/auth/userinfo.email',
].join(' ');

const OUTLOOK_SCOPES = [
  'https://graph.microsoft.com/Mail.Send',
  'https://graph.microsoft.com/Mail.Read',
  'https://graph.microsoft.com/User.Read',
].join(' ');

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

/**
 * Initiate OAuth flow by redirecting to provider's consent screen
 */
export async function initiateOAuth(provider: 'gmail' | 'outlook'): Promise<void> {
  try {
    const config = await getOAuthConfig(provider);
    
    // Generate state parameter for CSRF protection
    const state = generateRandomState();
    sessionStorage.setItem('oauth_state', state);
    sessionStorage.setItem('oauth_provider', provider);

    // Build authorization URL
    const params = new URLSearchParams({
      client_id: config.clientId,
      redirect_uri: config.redirectUri,
      response_type: 'code',
      scope: config.scope,
      state,
      access_type: 'offline', // Request refresh token
      prompt: 'consent', // Force consent screen to get refresh token
    });

    // Redirect to OAuth provider
    window.location.href = `${config.authUrl}?${params.toString()}`;
  } catch (error) {
    console.error('OAuth initiation failed:', error);
    throw error;
  }
}

/**
 * Handle OAuth callback and extract authorization code
 */
export function handleOAuthCallback(): { code: string; provider: 'gmail' | 'outlook' } | null {
  const params = new URLSearchParams(window.location.search);
  const code = params.get('code');
  const state = params.get('state');
  const error = params.get('error');

  // Check for errors
  if (error) {
    console.error('OAuth error:', error);
    return null;
  }

  // Validate state parameter
  const savedState = sessionStorage.getItem('oauth_state');
  if (!state || state !== savedState) {
    // This can happen in React Strict Mode (double useEffect execution)
    // or if user manually navigates to callback URL
    console.warn('OAuth state validation failed - callback may have already been processed');
    return null;
  }

  // Get provider
  const provider = sessionStorage.getItem('oauth_provider') as 'gmail' | 'outlook' | null;
  if (!provider || !code) {
    console.warn('Missing OAuth provider or authorization code');
    return null;
  }

  // Clean up session storage
  sessionStorage.removeItem('oauth_state');
  sessionStorage.removeItem('oauth_provider');

  return { code, provider };
}

/**
 * Generate random state parameter for CSRF protection
 */
function generateRandomState(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
}
