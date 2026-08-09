import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: process.env.VERCEL ? undefined : 'standalone',
  devIndicators: false,
  async rewrites() {
    // NOTE ON ARCHITECTURE (Aug 2026):
    // Every path the frontend or the MT5 EA uses has a dedicated Next.js API
    // route under web/pages/api (which proxies to ATE_BACKEND_URL). Next.js
    // resolves filesystem routes BEFORE fallback rewrites, so for those paths
    // the API route wins and the rewrites below never fire. They exist only as
    // a safety net for paths without a route file (e.g. /api/ai_scan_now,
    // /backend/*).
    //
    // WebSocket: rewrites do NOT tunnel WS upgrades on Vercel. The dashboard
    // realtime stream therefore connects to NEXT_PUBLIC_ATE_WS_URL (or derives
    // it from NEXT_PUBLIC_ATE_API_ORIGIN) instead of relying on a rewrite.
    const backendUrl = process.env.ATE_BACKEND_URL || 'http://127.0.0.1:8005';
    return [
      // MT5 EA sends to /api/v1/* — fallback rewrite straight to the backend
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
      {
        source: '/backend/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
