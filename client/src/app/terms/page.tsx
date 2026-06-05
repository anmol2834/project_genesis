import type { Metadata } from 'next';
import TermsPage from '@/components/legal/TermsPage';
import JsonLd from '@/components/shared/JsonLd';
import { buildMetadata, SITE_URL } from '@/lib/seo/metadata';
import { breadcrumbSchema } from '@/lib/seo/schema';

export const metadata: Metadata = buildMetadata({
  title: 'Terms & Conditions',
  description:
    'Read the Proxipilot Terms and Conditions. Understand your rights and obligations when using our AI-powered email automation platform.',
  path: '/terms',
});

export default function Terms() {
  return (
    <>
      <JsonLd
        data={breadcrumbSchema([
          { name: 'Home', url: SITE_URL },
          { name: 'Terms & Conditions', url: `${SITE_URL}/terms` },
        ])}
      />
      <TermsPage />
    </>
  );
}
