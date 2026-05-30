import type { Metadata } from 'next';
import { AppThemeProvider } from '@/providers/AppThemeProvider';
import { QueryProvider } from '@/lib/react-query/provider';
import { AuthProvider } from '@/contexts/AuthContext';
import '@/styles/globals.css';

export const metadata: Metadata = {
  title: 'Proxipilot',
  description: 'Next-generation mail automation platform',
  icons: {
    icon: '/Proxipilot-logo.ico',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning data-scroll-behavior="smooth">
      <body>
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
