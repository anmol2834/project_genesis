import type { Metadata } from 'next';
import { buildMetadata, SITE_URL } from '@/lib/seo/metadata';
import JsonLd from '@/components/shared/JsonLd';
import { pricingPageSchema, pricingFaqSchema, softwareApplicationSchema } from '@/lib/seo/schema';
import PricingClient from './PricingClient';

export const metadata: Metadata = buildMetadata({
  title: 'Pricing — Start Free, Scale When Ready | Proxipilot',
  description:
    'Proxipilot pricing: Free Starter (50 credits), Professional at $29/mo (500 credits), Growth at $39/mo (1,000 credits), and custom Enterprise. No hidden fees. Cancel anytime.',
  path: '/pricing',
  keywords: [
    'Proxipilot pricing',
    'AI email automation pricing',
    'email automation plans',
    'email automation cost',
    'AI email reply pricing',
    'Proxipilot plans',
    'email processing credits',
    'SaaS email pricing',
    'affordable email automation',
    'Proxipilot free plan',
  ],
});

export default function PricingPage() {
  return (
    <>
      <JsonLd
        data={[
          pricingFaqSchema(),
          pricingPageSchema(),
          softwareApplicationSchema(),
        ]}
      />
      <PricingClient />
    </>
  );
}
