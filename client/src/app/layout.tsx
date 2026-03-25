import type { Metadata } from 'next';
import { AppThemeProvider } from '@/providers/AppThemeProvider';
import { QueryProvider } from '@/lib/react-query/provider';
import '@/styles/globals.css';

export const metadata: Metadata = {
  title: 'Project Genesis',
  description: 'Next-generation mail automation platform',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth">
      <body>
        <QueryProvider>
          <AppThemeProvider>
            {children}
          </AppThemeProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
