import { SITE_URL, SITE_NAME } from './metadata';

export function organizationSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    '@id': `${SITE_URL}/#organization`,
    name: SITE_NAME,
    url: SITE_URL,
    logo: {
      '@type': 'ImageObject',
      '@id': `${SITE_URL}/#logo`,
      url: `${SITE_URL}/Proxipilot-logo.ico`,
      contentUrl: `${SITE_URL}/Proxipilot-logo.ico`,
      caption: SITE_NAME,
    },
    description:
      'Proxipilot is an AI-powered email automation platform that generates smart replies before you open your inbox.',
    sameAs: [
      'https://twitter.com/proxipilot',
      'https://linkedin.com/company/proxipilot',
    ],
    contactPoint: {
      '@type': 'ContactPoint',
      contactType: 'customer support',
      url: `${SITE_URL}/waitlist`,
    },
  };
}

export function websiteSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    '@id': `${SITE_URL}/#website`,
    name: SITE_NAME,
    url: SITE_URL,
    publisher: {
      '@id': `${SITE_URL}/#organization`,
    },
  };
}

export function softwareApplicationSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    '@id': `${SITE_URL}/#softwareapplication`,
    name: SITE_NAME,
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web',
    url: SITE_URL,
    description:
      'AI-powered email automation platform that generates replies before you open the email. Blazing fast processing, smart tone learning, enterprise-grade inbox management.',
    brand: {
      '@type': 'Brand',
      name: SITE_NAME,
    },
    offers: {
      '@type': 'AggregateOffer',
      priceCurrency: 'USD',
      offerCount: 4,
      lowPrice: '0',
      highPrice: '39',
      offers: [
        {
          '@type': 'Offer',
          name: 'Starter',
          description: 'Free plan — 50 email processing credits, 1 email account, AI reply generation.',
          price: '0',
          priceCurrency: 'USD',
          priceSpecification: { '@type': 'UnitPriceSpecification', price: '0', priceCurrency: 'USD', unitText: 'MONTH' },
          url: `${SITE_URL}/sign-up`,
          availability: 'https://schema.org/InStock',
        },
        {
          '@type': 'Offer',
          name: 'Professional',
          description: 'Professional plan — 500 email processing credits/month, 3 accounts, 2,000 leads, CRM integrations.',
          price: '29',
          priceCurrency: 'USD',
          priceSpecification: { '@type': 'UnitPriceSpecification', price: '29', priceCurrency: 'USD', unitText: 'MONTH' },
          url: `${SITE_URL}/sign-up`,
          availability: 'https://schema.org/InStock',
        },
        {
          '@type': 'Offer',
          name: 'Growth',
          description: 'Growth plan — 1,000 email processing credits/month, 5 accounts, 3,000 leads, advanced AI features.',
          price: '39',
          priceCurrency: 'USD',
          priceSpecification: { '@type': 'UnitPriceSpecification', price: '39', priceCurrency: 'USD', unitText: 'MONTH' },
          url: `${SITE_URL}/sign-up`,
          availability: 'https://schema.org/InStock',
        },
        {
          '@type': 'Offer',
          name: 'Enterprise',
          description: 'Enterprise plan — Custom credits, dedicated infrastructure, custom AI training, white-label, dedicated CSM.',
          price: '0',
          priceCurrency: 'USD',
          priceSpecification: { '@type': 'UnitPriceSpecification', price: '0', priceCurrency: 'USD', unitText: 'MONTH' },
          url: `${SITE_URL}/pricing`,
          availability: 'https://schema.org/InStock',
        },
      ],
    },
    provider: {
      '@id': `${SITE_URL}/#organization`,
    },
    featureList: [
      'AI-powered email reply generation',
      '< 15s response time',
      'Smart tone learning',
      'Campaign inbox management',
      'Multi-account support',
      'Advanced analytics dashboard',
      'Team collaboration tools',
      'Custom AI training',
      'AES-256 token encryption',
      'CRM & third-party integrations',
    ],
  };
}

export function breadcrumbSchema(items: { name: string; url: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      item: item.url,
    })),
  };
}

export function faqSchema(items: { question: string; answer: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: items.map((item) => ({
      '@type': 'Question',
      name: item.question,
      acceptedAnswer: { '@type': 'Answer', text: item.answer },
    })),
  };
}

export function articleSchema({
  title,
  description,
  url,
  datePublished,
  dateModified,
  image,
}: {
  title: string;
  description: string;
  url: string;
  datePublished: string;
  dateModified?: string;
  image?: string;
}) {
  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: title,
    description,
    url,
    datePublished,
    dateModified: dateModified ?? datePublished,
    image: image ?? `${SITE_URL}/og-default.png`,
    author: { '@type': 'Organization', name: SITE_NAME, url: SITE_URL },
    publisher: {
      '@id': `${SITE_URL}/#organization`,
    },
  };
}

export function pricingPageSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    '@id': `${SITE_URL}/pricing#webpage`,
    name: 'Proxipilot Pricing — Simple, Transparent Plans',
    description:
      'Compare Proxipilot plans. Start free with 50 credits, scale to 500 credits/mo ($29) or 1,000 credits/mo ($39). Custom Enterprise pricing available.',
    url: `${SITE_URL}/pricing`,
    isPartOf: { '@id': `${SITE_URL}/#website` },
    about: { '@id': `${SITE_URL}/#softwareapplication` },
    breadcrumb: {
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Home',    item: SITE_URL },
        { '@type': 'ListItem', position: 2, name: 'Pricing', item: `${SITE_URL}/pricing` },
      ],
    },
    mainEntity: {
      '@type': 'ItemList',
      name: 'Proxipilot Pricing Plans',
      description: 'All available pricing plans for Proxipilot AI email automation',
      numberOfItems: 4,
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          item: {
            '@type': 'Offer',
            name: 'Starter Plan',
            description: 'Free plan with 50 email processing credits. Includes AI reply generation, unified inbox, and CSV lead import. No credit card required.',
            price: '0',
            priceCurrency: 'USD',
            priceSpecification: { '@type': 'UnitPriceSpecification', price: '0', priceCurrency: 'USD', unitText: 'MONTH' },
            url: `${SITE_URL}/sign-up`,
            availability: 'https://schema.org/InStock',
            seller: { '@id': `${SITE_URL}/#organization` },
          },
        },
        {
          '@type': 'ListItem',
          position: 2,
          item: {
            '@type': 'Offer',
            name: 'Professional Plan',
            description: '$29/month. 500 email processing credits, 3 email accounts, 2,000 leads, context memory, CRM integrations, My Data vault, team up to 5 members, priority email support.',
            price: '29',
            priceCurrency: 'USD',
            priceSpecification: { '@type': 'UnitPriceSpecification', price: '29', priceCurrency: 'USD', unitText: 'MONTH' },
            url: `${SITE_URL}/sign-up`,
            availability: 'https://schema.org/InStock',
            seller: { '@id': `${SITE_URL}/#organization` },
          },
        },
        {
          '@type': 'ListItem',
          position: 3,
          item: {
            '@type': 'Offer',
            name: 'Growth Plan',
            description: '$39/month. 1,000 email processing credits, 5 email accounts, 3,000 leads, 15 campaigns, CRM integrations, My Data vault, team up to 10 members, priority email and chat support.',
            price: '39',
            priceCurrency: 'USD',
            priceSpecification: { '@type': 'UnitPriceSpecification', price: '39', priceCurrency: 'USD', unitText: 'MONTH' },
            url: `${SITE_URL}/sign-up`,
            availability: 'https://schema.org/InStock',
            seller: { '@id': `${SITE_URL}/#organization` },
          },
        },
        {
          '@type': 'ListItem',
          position: 4,
          item: {
            '@type': 'Offer',
            name: 'Enterprise Plan',
            description: 'Custom pricing. Custom email credits, dedicated infrastructure, custom AI training, RBAC, compliance logs, white-label, and dedicated customer success manager.',
            price: '0',
            priceCurrency: 'USD',
            url: `${SITE_URL}/pricing`,
            availability: 'https://schema.org/InStock',
            seller: { '@id': `${SITE_URL}/#organization` },
          },
        },
      ],
    },
  };
}

export function pricingFaqSchema() {
  return faqSchema([
    {
      question: 'What is an email processing credit?',
      answer: 'One credit equals one email processed by the Proxipilot AI engine — including reading the email, understanding context, and generating a smart reply draft.',
    },
    {
      question: 'How much does Proxipilot cost?',
      answer: 'Proxipilot offers a free Starter plan with 50 credits, a Professional plan at $29/month with 500 credits, a Growth plan at $39/month with 1,000 credits, and custom Enterprise pricing.',
    },
    {
      question: 'Can I change my plan later?',
      answer: 'Yes. You can upgrade or downgrade your Proxipilot plan at any time from your billing settings. Changes take effect on your next billing cycle.',
    },
    {
      question: 'Is there a free trial for paid plans?',
      answer: 'The Starter plan is permanently free with 50 credits — no credit card required. It lets you experience the full AI email workflow before upgrading.',
    },
    {
      question: 'What happens when I run out of credits?',
      answer: "You'll receive an alert when credits are running low. You can purchase top-up credit packs or upgrade to a higher plan at any time.",
    },
    {
      question: 'Do unused credits roll over?',
      answer: 'Credits reset monthly on your billing date and do not roll over. You can top up at any time if you need more before the monthly reset.',
    },
    {
      question: 'How does Enterprise pricing work?',
      answer: 'Enterprise is fully custom — tailored to your volume, compliance requirements, and team size. Contact sales at sales@proxipilot.ai to get a quote.',
    },
  ]);
}
