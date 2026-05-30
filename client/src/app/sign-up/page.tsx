import type { Metadata } from 'next';
import SignUpPage from '@/components/auth/SignUpPage';

export const metadata: Metadata = {
  title: 'Create account — Proxipilot',
  description: 'Set up your AI-powered email automation in minutes.',
};

export default function Page() {
  return <SignUpPage />;
}
