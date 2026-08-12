import type { NextConfig } from 'next';

/*
 * ATE Architecture:
 * 
 * Canonical URL Structure (Vercel Deployment):
 *   Website : https://autonomous-trading-engine.vercel.app/
 *   Backend : https://autonomous-trading-engine.vercel.app/backend
 *   API/v1  : https://autonomous-trading-engine.vercel.app/api/v1
 * 
 * Flow:
 *   Browser → Vercel (Frontend) → Vercel Backend (server.py)
 *   MT5 EA → Vercel /api/v1/* (server.py handles routing)
 * 
 * Local Development:
 *   ATE_BACKEND_URL=http://127.0.0.1:8005 (dashboard server)
 */

// BUG FIX: fallback cũ = 'https://...vercel.app/backend' — nếu chạy LOCAL mà env
// ATE_BACKEND_URL không được set (web/.env thiếu) thì web âm thầm proxy lên cloud
// → dashboard đọc backend SAI (không có telemetry EA) dù EA gửi đúng. Cũng tạo
// vòng lặp tự tham chiếu khi deploy Vercel thiếu env. Đổi fallback về LOCAL 8005
// (khớp api-config.ts + web/.env). Vercel production luôn set env qua vercel.json.
const ATE_BACKEND_URL = process.env.ATE_BACKEND_URL || 'http://localhost:8005';
const ATE_MT5_API    = process.env.ATE_MT5_API    || 'http://localhost:8005/api/v1';

const nextConfig: NextConfig = {
  output: process.env.VERCEL ? undefined : 'standalone',
  devIndicators: false,

  async rewrites() {
    return [
      // MT5 EA sends to /api/v1/* — rewrite to backend server
      // BUG FIX: EA gọi POST /api/v1/telemetry (thiếu /bridge); backend route là
      // /api/v1/bridge/telemetry — trước đây destination sai => EA 404 => MT5 NO.
      {
        source: '/api/v1/telemetry',
        destination: `${ATE_MT5_API}/bridge/telemetry`,
      },
      {
        source: '/api/v1/bridge/commands/claim',
        destination: `${ATE_MT5_API}/bridge/commands/claim`,
      },
      {
        source: '/api/v1/bridge/candles',
        destination: `${ATE_MT5_API}/bridge/candles`,
      },
      {
        source: '/api/v1/bridge/markup',
        destination: `${ATE_MT5_API}/bridge/markup`,
      },
      {
        source: '/api/v1/bridge/calendar',
        destination: `${ATE_MT5_API}/bridge/calendar`,
      },
      {
        source: '/api/v1/bridge/commands/:commandId/receipt',
        destination: `${ATE_MT5_API}/bridge/commands/:commandId/receipt`,
      },
      // Standard API proxy (Vercel → backend)
      {
        source: '/api/:path*',
        destination: `${ATE_BACKEND_URL}/api/:path*`,
      },
      // /backend/* proxy (self-referential on Vercel — server.py handles)
      {
        source: '/backend/:path*',
        destination: `${ATE_BACKEND_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
