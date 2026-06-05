import type { Metadata } from 'next';

export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || 'https://proxipilot.ai';
export const SITE_NAME = 'Proxipilot';
export const TWITTER_HANDLE = '@proxipilot';
export const DEFAULT_OG_IMAGE = `${SITE_URL}/og-default.png`;

const baseRobots: Metadata['robots'] = {
  index: true,
  follow: true,
  googleBot: {
    index: true,
    follow: true,
    'max-image-preview': 'large',
    'max-snippet': -1,
    'max-video-preview': -1,
  },
};

const noIndexRobots: Metadata['robots'] = {
  index: false,
  follow: false,
  googleBot: { index: false, follow: false },
};

interface PageMetaOptions {
  title: string;
  description: string;
  path?: string;
  image?: string;
  noIndex?: boolean;
  keywords?: string[];
  ogType?: 'website' | 'article';
}

export function buildMetadata({
  title,
  description,
  path = '',
  image,
  noIndex = false,
  keywords,
  ogType = 'website',
}: PageMetaOptions): Metadata {
  const url = `${SITE_URL}${path}`;
  const ogImage = image ?? DEFAULT_OG_IMAGE;

  return {
    metadataBase: new URL(SITE_URL),
    title,
    description,
    applicationName: SITE_NAME,
    authors: [{ name: SITE_NAME, url: SITE_URL }],
    publisher: SITE_NAME,
    category: 'Technology',
    referrer: 'origin-when-cross-origin',
    formatDetection: { email: false, telephone: false },
    ...(keywords && { keywords }),
    alternates: { canonical: url },
    robots: noIndex ? noIndexRobots : baseRobots,
    openGraph: {
      type: ogType,
      siteName: SITE_NAME,
      locale: 'en_US',
      title,
      description,
      url,
      images: [{ url: ogImage, width: 1200, height: 630, alt: title }],
    },
    twitter: {
      card: 'summary_large_image',
      site: TWITTER_HANDLE,
      creator: TWITTER_HANDLE,
      title,
      description,
      images: [ogImage],
    },
  };
}
