import type { Metadata } from 'next';
import dynamic from 'next/dynamic';
import Navbar from '@/components/landing/Navbar';
import HeroSection from '@/components/landing/HeroSection';
import Footer from '@/components/landing/Footer';
import FloatingWaitlistButton from '@/components/landing/FloatingWaitlistButton';
import JsonLd from '@/components/shared/JsonLd';
import { buildMetadata } from '@/lib/seo/metadata';
import { softwareApplicationSchema, breadcrumbSchema } from '@/lib/seo/schema';
import { SITE_URL } from '@/lib/seo/metadata';

const HowItWorksSection = dynamic(() => import('@/components/landing/HowItWorksSection'));
const AISection         = dynamic(() => import('@/components/landing/AISection'));
const FeaturesSection   = dynamic(() => import('@/components/landing/FeaturesSection'));
const StatsSection      = dynamic(() => import('@/components/landing/StatsSection'));
const InboxSection      = dynamic(() => import('@/components/landing/InboxSection'));
const PricingSection    = dynamic(() => import('@/components/landing/PricingSection'));
const CTASection        = dynamic(() => import('@/components/landing/CTASection'));

export const metadata: Metadata = buildMetadata({
  title: 'Proxipilot — AI Email Automation Platform',
  description:
    'Proxipilot automatically generates smart email replies before you open your inbox. Save 20+ hours per week with blazing-fast AI processing and intelligent tone learning.',
  path: '/',
  keywords: [
    'Proxipilot',
    'AI email automation',
    'email automation platform',
    'automated email replies',
    'AI inbox management',
    'enterprise email automation',
    'email productivity SaaS',
    'smart email replies',
  ],
});

export default function LandingPage() {
  return (
    <>
      <JsonLd
        data={[
          softwareApplicationSchema(),
          breadcrumbSchema([{ name: 'Home', url: SITE_URL }]),
        ]}
      />
      <Navbar />
      <main>
        <HeroSection />
        <HowItWorksSection />
        <AISection />
        <FeaturesSection />
        <StatsSection />
        <InboxSection />
        <PricingSection />
        <CTASection />
      </main>
      <Footer />
      <FloatingWaitlistButton />
    </>
  );
}
