import dynamic from 'next/dynamic';
import Navbar from '@/components/landing/Navbar';
import HeroSection from '@/components/landing/HeroSection';
import Footer from '@/components/landing/Footer';
import FloatingWaitlistButton from '@/components/landing/FloatingWaitlistButton';

const HowItWorksSection = dynamic(() => import('@/components/landing/HowItWorksSection'));
const AISection         = dynamic(() => import('@/components/landing/AISection'));
const FeaturesSection   = dynamic(() => import('@/components/landing/FeaturesSection'));
const StatsSection      = dynamic(() => import('@/components/landing/StatsSection'));
const InboxSection      = dynamic(() => import('@/components/landing/InboxSection'));
const PricingSection    = dynamic(() => import('@/components/landing/PricingSection'));
const CTASection        = dynamic(() => import('@/components/landing/CTASection'));

export default function LandingPage() {
  return (
    <>
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
