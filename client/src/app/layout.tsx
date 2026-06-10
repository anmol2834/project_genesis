import type { Metadata, Viewport } from 'next';
import { AppThemeProvider } from '@/providers/AppThemeProvider';
import { QueryProvider } from '@/lib/react-query/provider';
import { AuthProvider } from '@/contexts/AuthContext';
import JsonLd from '@/components/shared/JsonLd';
import { organizationSchema, websiteSchema } from '@/lib/seo/schema';
import { SITE_URL, SITE_NAME } from '@/lib/seo/metadata';
import '@/styles/globals.css';

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: `${SITE_NAME} — AI Email Automation Platform`,
    template: `%s | ${SITE_NAME}`,
  },
  description:
    'Proxipilot automatically generates smart email replies before you open your inbox. Save 20+ hours per week with blazing-fast AI processing and intelligent tone learning.',
  applicationName: SITE_NAME,
  authors: [{ name: SITE_NAME, url: SITE_URL }],
  publisher: SITE_NAME,
  category: 'Technology',
  referrer: 'origin-when-cross-origin',
  formatDetection: { email: false, telephone: false },
  keywords: [
    'AI email automation',
    'email automation platform',
    'AI inbox management',
    'automated email replies',
    'enterprise email AI',
    'email productivity tool',
    'SaaS email automation',
  ],
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-image-preview': 'large',
      'max-snippet': -1,
      'max-video-preview': -1,
    },
  },
  openGraph: {
    type: 'website',
    siteName: SITE_NAME,
    locale: 'en_US',
    title: `${SITE_NAME} — AI Email Automation Platform`,
    description:
      'AI-powered email automation that generates replies before you open your inbox. Blazing fast processing, smart tone learning.',
    url: SITE_URL,
    images: [
      {
        url: `${SITE_URL}/og-default.png`,
        width: 1200,
        height: 630,
        alt: `${SITE_NAME} — AI Email Automation Platform`,
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    site: '@proxipilot',
    creator: '@proxipilot',
    title: `${SITE_NAME} — AI Email Automation Platform`,
    description:
      'AI-powered email automation that generates replies before you open your inbox.',
    images: [`${SITE_URL}/og-default.png`],
  },
  icons: {
    icon: [
      { url: '/favicon.ico', rel: 'shortcut icon' },
      { url: '/favicon-96x96.png', sizes: '96x96', type: 'image/png' },
      { url: '/favicon.svg', type: 'image/svg+xml' },
    ],
    apple: [{ url: '/apple-touch-icon.png', sizes: '180x180' }],
  },
  manifest: '/site.webmanifest',
  alternates: { canonical: SITE_URL },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#080d18' },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth">
      <body>
        <JsonLd data={[organizationSchema(), websiteSchema()]} />
        <QueryProvider>
          <AppThemeProvider>
            <AuthProvider>
              {children}
            </AuthProvider>
          </AppThemeProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
