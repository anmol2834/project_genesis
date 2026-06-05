import { SITE_URL, SITE_NAME } from './metadata';

export function organizationSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: SITE_NAME,
    url: SITE_URL,
    logo: {
      '@type': 'ImageObject',
      url: `${SITE_URL}/Proxipilot logo.svg`,
      width: 200,
      height: 200,
    },
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
    name: SITE_NAME,
    url: SITE_URL,
    potentialAction: {
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: `${SITE_URL}/?q={search_term_string}`,
      },
      'query-input': 'required name=search_term_string',
    },
  };
}

export function softwareApplicationSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: SITE_NAME,
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web',
    url: SITE_URL,
    description:
      'AI-powered email automation platform that generates replies before you open the email. Sub-25ms processing, smart tone learning, enterprise-grade inbox management.',
    offers: {
      '@type': 'AggregateOffer',
      priceCurrency: 'USD',
      offerCount: 3,
      lowPrice: '0',
      offers: [
        { '@type': 'Offer', name: 'Starter', price: '0', priceCurrency: 'USD' },
        { '@type': 'Offer', name: 'Professional', price: 'TBD', priceCurrency: 'USD' },
        { '@type': 'Offer', name: 'Enterprise', price: 'TBD', priceCurrency: 'USD' },
      ],
    },
    provider: {
      '@type': 'Organization',
      name: SITE_NAME,
      url: SITE_URL,
    },
    featureList: [
      'AI-powered email reply generation',
      'Sub-25ms response time',
      'Smart tone learning',
      'Campaign inbox management',
      'Multi-account support',
      'Advanced analytics dashboard',
      'Team collaboration tools',
      'Custom AI training',
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
      '@type': 'Organization',
      name: SITE_NAME,
      logo: { '@type': 'ImageObject', url: `${SITE_URL}/Proxipilot logo.svg` },
    },
  };
}
