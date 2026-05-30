import type { Metadata } from 'next';
import SignInPage from '@/components/auth/SignInPage';

export const metadata: Metadata = {
  title: 'Sign in — Proxipilot',
  description: 'Sign in to your Proxipilot account',
};

export default function Page() {
  return <SignInPage />;
}
