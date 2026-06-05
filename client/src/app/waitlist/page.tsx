import type { Metadata } from 'next';
import { buildMetadata, SITE_URL } from '@/lib/seo/metadata';
import JsonLd from '@/components/shared/JsonLd';
import { breadcrumbSchema } from '@/lib/seo/schema';
import WaitlistClient from './WaitlistClient';

export const metadata: Metadata = buildMetadata({
  title: 'Join the Waitlist — Early Access to AI Email Automation',
  description:
    'Secure your spot on the Proxipilot waitlist. Join 2,500+ early adopters for exclusive access to AI-powered email automation that saves 20+ hours per week.',
  path: '/waitlist',
  keywords: ['AI email automation waitlist', 'Proxipilot early access', 'email automation beta'],
});

export default function WaitlistPage() {
  return (
    <>
      <JsonLd
        data={breadcrumbSchema([
          { name: 'Home', url: SITE_URL },
          { name: 'Waitlist', url: `${SITE_URL}/waitlist` },
        ])}
      />
      <WaitlistClient />
    </>
  );
}
