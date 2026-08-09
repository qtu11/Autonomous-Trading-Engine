import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: process.env.VERCEL ? undefined : 'standalone',
  devIndicators: false,
  async rewrites() {
    const backendUrl = process.env.ATE_BACKEND_URL || 'http://127.0.0.1:8005';
    return [
      // MT5 EA sends to /api/v1/* — Vercel rewrites directly to backend
      // Bypass Next.js serverless body handling (which fails for MT5 POST requests)
      // because Vercel serverless cannot stream raw POST bodies to upstream.
      // Rewrite goes through Vercel's nginx which forwards the raw HTTP request.
      {
        source: '/api/v1/telemetry',
        destination: `${backendUrl}/api/v1/telemetry`,
      },
      {
        source: '/api/v1/bridge/commands/claim',
        destination: `${backendUrl}/api/v1/bridge/commands/claim`,
      },
      {
        source: '/api/v1/bridge/candles',
        destination: `${backendUrl}/api/v1/bridge/candles`,
      },
      {
        source: '/api/v1/bridge/markup',
        destination: `${backendUrl}/api/v1/bridge/markup`,
      },
      {
        source: '/api/v1/bridge/calendar',
        destination: `${backendUrl}/api/v1/bridge/calendar`,
      },
      {
        source: '/api/v1/bridge/commands/:commandId/receipt',
        destination: `${backendUrl}/api/v1/bridge/commands/:commandId/receipt`,
      },
      // Standard browser API proxy
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: '/backend/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
