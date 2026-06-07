import type { Metadata } from 'next';
import RefundPage from '@/components/legal/RefundPage';
import JsonLd from '@/components/shared/JsonLd';
import { buildMetadata, SITE_URL } from '@/lib/seo/metadata';
import { breadcrumbSchema } from '@/lib/seo/schema';

export const metadata: Metadata = buildMetadata({
  title: 'Refund & Cancellation Policy',
  description:
    'Learn about Proxipilot\'s refund, cancellation, subscription, billing, and credit usage policies.',
  path: '/refund',
  keywords: [
    'refund policy',
    'cancellation policy',
    'subscription billing',
    'Proxipilot refund',
    'money back',
    'cancel subscription',
  ],
});

export default function Refund() {
  return (
    <>
      <JsonLd
        data={breadcrumbSchema([
          { name: 'Home', url: SITE_URL },
          { name: 'Refund & Cancellation Policy', url: `${SITE_URL}/refund` },
        ])}
      />
      <RefundPage />
    </>
  );
}
