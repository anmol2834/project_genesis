import type { Metadata } from 'next';
import SignInPage from '@/components/auth/SignInPage';
import { buildMetadata } from '@/lib/seo/metadata';

export const metadata: Metadata = buildMetadata({
  title: 'Sign In',
  description: 'Sign in to your Proxipilot account to access your AI-powered email automation dashboard.',
  path: '/sign-in',
});

export default function Page() {
  return <SignInPage />;
}
