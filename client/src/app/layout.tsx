import type { Metadata } from 'next';
import { AppThemeProvider } from '@/providers/AppThemeProvider';
import '@/styles/globals.css';

export const metadata: Metadata = {
  title: 'Project Genesis',
  description: 'Next-generation mail automation platform',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth">
      <body>
        <AppThemeProvider>
          {children}
        </AppThemeProvider>
      </body>
    </html>
  );
}
