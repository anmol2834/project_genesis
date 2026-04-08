import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactCompiler: true,
  transpilePackages: ['@mui/material', '@mui/icons-material', '@mui/system'],
  experimental: {
    optimizePackageImports: ['@mui/material', '@mui/icons-material'],
  },
  logging: {
    fetches: { fullUrl: false },
  },
};

export default nextConfig;
