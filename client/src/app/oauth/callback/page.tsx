import type { Metadata } from 'next';
import OAuthCallbackClient from './OAuthCallbackClient';
import { buildMetadata } from '@/lib/seo/metadata';

export const metadata: Metadata = buildMetadata({
  title: 'Connecting Account',
  description: 'Connecting your email account to Proxipilot.',
  path: '/oauth/callback',
  noIndex: true,
});

export default function OAuthCallbackPage() {
  return <OAuthCallbackClient />;
}
