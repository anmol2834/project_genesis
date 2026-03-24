import type { Metadata } from 'next';
import SignInPage from '@/components/auth/SignInPage';

export const metadata: Metadata = {
  title: 'Sign in — MailFlowAI',
  description: 'Sign in to your MailFlowAI account',
};

export default function Page() {
  return <SignInPage />;
}
