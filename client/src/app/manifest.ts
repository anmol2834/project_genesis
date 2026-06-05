import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Proxipilot — AI Email Automation',
    short_name: 'Proxipilot',
    description: 'AI-powered email automation platform. Generate replies before you open your inbox.',
    start_url: '/',
    display: 'standalone',
    background_color: '#080d18',
    theme_color: '#7c3aed',
    orientation: 'portrait',
    icons: [
      {
        src: '/Proxipilot-logo.ico',
        sizes: 'any',
        type: 'image/x-icon',
      },
      {
        src: '/Proxipilot logo.svg',
        sizes: 'any',
        type: 'image/svg+xml',
        purpose: 'maskable',
      },
    ],
  };
}
