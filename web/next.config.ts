import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: process.env.VERCEL ? undefined : 'standalone',
  devIndicators: false,
  turbopack: {
    root: __dirname,
  },
  async rewrites() {
    const backendUrl = process.env.ATE_BACKEND_URL || 'http://127.0.0.1:8005';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
