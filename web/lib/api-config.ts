/// <reference types="node" />

export const BACKEND_URL =
  process.env.ATE_BACKEND_URL || 'http://113.173.192.226:8848';

export const ATE_MT5_API =
  process.env.ATE_MT5_API ||
  'https://autonomous-trading-engine.vercel.app/api/v1';

export const ATE_BACKEND_URL = BACKEND_URL;

export const ATE_FRONTEND_URL =
  process.env.ATE_FRONTEND_URL ||
  'https://autonomous-trading-engine.vercel.app';
