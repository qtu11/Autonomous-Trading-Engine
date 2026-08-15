/// <reference types="node" />

/**
 * Backend configuration.
 *
 * Two flows are supported:
 * 1. Direct: browser → FastAPI on VPS (CORS needed)
 * 2. Proxy:  browser → Vercel (next.config.ts rewrites) → FastAPI on VPS
 *
 * Default = proxy so browser only talks to the frontend origin.
 *
 * Port chuẩn (ENVIRONMENT_CONFIG.md):
 *  - Backend FastAPI luôn chạy 8005 (local + Cloudlocal).
 *  - 8848 chỉ là cổng public của nginx trên home server (production).
 * BUG FIX: trước đây local dev fallback về 8848 trong khi start.ps1 chạy backend
 * 8005 → toàn bộ proxy 502. Giờ ưu tiên ATE_BACKEND_URL (mọi môi trường), fallback
 * 8005 ở dev, 8848 ở production.
 */

const isLocalDev = process.env.NODE_ENV === 'development' || !process.env.VERCEL;
const envBackend = (process.env.ATE_BACKEND_URL || '').trim();

export const BACKEND_URL = (envBackend || (isLocalDev ? 'http://127.0.0.1:8005' : 'http://127.0.0.1:8848')).replace(/\/+$/, '');

/**
 * Browser-facing base URL. When empty, all fetches go to relative /api/*
 * which is rewritten/proxied by Next.js catch-all to BACKEND_URL.
 */
const publicOrigin = (process.env.NEXT_PUBLIC_ATE_API_ORIGIN || '').trim();

export const ATE_MT5_API =
  process.env.ATE_MT5_API ||
  (publicOrigin
    ? `${publicOrigin.replace(/\/+$/, '')}/api/v1`
    : '/api/v1');

export const ATE_BACKEND_URL = BACKEND_URL;

export const ATE_FRONTEND_URL =
  process.env.ATE_FRONTEND_URL ||
  'https://autonomous-trading-engine.vercel.app';
