import type { Metadata } from 'next';
import PrivacyPage from '@/components/legal/PrivacyPage';
import JsonLd from '@/components/shared/JsonLd';
import { buildMetadata, SITE_URL } from '@/lib/seo/metadata';
import { breadcrumbSchema } from '@/lib/seo/schema';

export const metadata: Metadata = buildMetadata({
  title: 'Privacy Policy',
  description:
    'Read the Proxipilot Privacy Policy. Learn how we collect, use, and protect your data on our AI-powered email automation platform.',
  path: '/privacy',
});

export default function Privacy() {
  return (
    <>
      <JsonLd
        data={breadcrumbSchema([
          { name: 'Home', url: SITE_URL },
          { name: 'Privacy Policy', url: `${SITE_URL}/privacy` },
        ])}
      />
      <PrivacyPage />
    </>
  );
}
