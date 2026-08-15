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

// BUG FIX: fallback theo đúng chuẩn ENVIRONMENT_CONFIG.md — local dev backend
// chạy 8005. Production (Vercel/nginx) BẮT BUỘC set ATE_BACKEND_URL — trước
// đây fallback localhost:8848 âm thầm khiến mọi API 502 trên Vercel khi quên
// env. Giờ fail-fast: build production thiếu env → lỗi rõ ràng thay vì 502 mù.
const IS_DEV = process.env.NODE_ENV === 'development';
const IS_PROD = !IS_DEV;
const ATE_BACKEND_URL = process.env.ATE_BACKEND_URL || (IS_DEV ? 'http://localhost:8005' : (() => {
  throw new Error('ATE_BACKEND_URL bắt buộc phải set khi build production (Vercel: http://<IP>:8848 hoặc URL backend). Xem ENVIRONMENT_CONFIG.md');
})());
const ATE_MT5_API    = process.env.ATE_MT5_API    || `${ATE_BACKEND_URL.replace(/\/+$/, '')}/api/v1`;

const nextConfig: NextConfig = {
  output: process.env.VERCEL ? undefined : 'standalone',
  devIndicators: false,

  async rewrites() {
    return [
      // BUG FIX: bỏ các rewrite /api/v1/bridge/* — chúng bị shadow bởi file
      // pages/api/v1/bridge/*.ts (rewrites mặc định chạy SAU filesystem) nên
      // không bao giờ kích hoạt. Chỉ giữ rewrite receipt (không có file tương
      // ứng) + catch-all cho đường /api/* không có file proxy.
      {
        source: '/api/v1/bridge/commands/:commandId/receipt',
        destination: `${ATE_MT5_API}/bridge/commands/:commandId/receipt`,
      },
      // Standard API proxy (Vercel → backend) cho đường /api/* không có file
      // pages/api — file proxy (có auth JWT) luôn được ưu tiên.
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
