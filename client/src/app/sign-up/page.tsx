import type { Metadata } from 'next';
import SignUpPage from '@/components/auth/SignUpPage';
import { buildMetadata } from '@/lib/seo/metadata';

export const metadata: Metadata = buildMetadata({
  title: 'Create Account',
  description: 'Create your Proxipilot account and set up AI-powered email automation in minutes.',
  path: '/sign-up',
});

export default function Page() {
  return <SignUpPage />;
}
