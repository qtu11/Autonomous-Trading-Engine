/// <reference types="node" />

/**
 * Backend configuration.
 *
 * Two flows are supported:
 * 1. Direct: browser → FastAPI on VPS (CORS needed)
 * 2. Proxy:  browser → Vercel (next.config.ts rewrites) → FastAPI on VPS
 *
 * Default = proxy through Vercel so browser only talks to vercel.app.
 * Production: env ATE_BACKEND_URL set via vercel.json → 8848.
 * Local dev: fallback localhost:8848 (chuẩn mới, khớp VPS + Docker).
 */

const isLocalDev = process.env.NODE_ENV === 'development' || !process.env.VERCEL;
const envBackend = (process.env.ATE_BACKEND_URL || '').trim();

/**
 * If NEXT_PUBLIC_ATE_API_ORIGIN is set (frontend wants to talk to backend
 * directly), use that. Otherwise go through Vercel's own domain via /api.
 */
const publicOrigin = (process.env.NEXT_PUBLIC_ATE_API_ORIGIN || '').trim();

// In local development, prefer 127.0.0.1:8848 to avoid NAT loopback / WAN ETIMEDOUT
export const BACKEND_URL = (isLocalDev ? (process.env.LOCAL_BACKEND_URL || 'http://127.0.0.1:8848') : (envBackend || 'http://127.0.0.1:8848')).replace(/\/+$/, '');

/**
 * Browser-facing base URL. When empty, all fetches go to relative /api/*
 * which is rewritten/proxied by Next.js catch-all to BACKEND_URL.
 */
export const ATE_MT5_API =
  process.env.ATE_MT5_API ||
  (publicOrigin
    ? `${publicOrigin.replace(/\/+$/, '')}/api/v1`
    : '/api/v1');

export const ATE_BACKEND_URL = BACKEND_URL;

export const ATE_FRONTEND_URL =
  process.env.ATE_FRONTEND_URL ||
  'https://autonomous-trading-engine.vercel.app';