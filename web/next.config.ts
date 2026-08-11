import type { NextConfig } from 'next';

/*
 * ATE Architecture (Aug 2026):
 * 
 * URLs:
 *   Website : https://autonomous-trading-engine.vercel.app/
 *   Backend : https://autonomous-trading-engine.vercel.app/backend
 *   API/v1 : https://autonomous-trading-engine.vercel.app/api/v1
 * 
 * Frontend calls API via:
 *   1. Next.js API routes (web/pages/api/*) - PROXY to ATE_BACKEND_URL
 *   2. Direct browser calls using NEXT_PUBLIC_ATE_API_ORIGIN
 *   3. Rewrites for /backend/* and /api/v1/* fallback
 * 
 * MT5 EA sends to: /api/v1/* → proxied via Next.js
 */

const nextConfig: NextConfig = {
  output: process.env.VERCEL ? undefined : 'standalone',
  devIndicators: false,

  async rewrites() {
    const backendUrl = process.env.ATE_BACKEND_URL || 'https://autonomous-trading-engine.vercel.app/backend';
    
    return [
      // MT5 EA sends to /api/v1/* — rewrite to backend
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
      // Standard browser API proxy (fallback for paths without route files)
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      // /backend/* proxy
      {
        source: '/backend/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
