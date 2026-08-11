// Shared API Configuration for all API routes

// Backend URL - points to home server
export const BACKEND_URL =
  process.env.ATE_BACKEND_URL || 'http://113.173.192.226:8848';

// MT5 API - through Vercel rewrite
export const ATE_MT5_API =
  process.env.ATE_MT5_API || 'https://autonomous-trading-engine.vercel.app/api/v1';