/// <reference types="node" />

/// <reference types="node" />

const rawBackendUrl = process.env.ATE_BACKEND_URL || 'http://localhost:8005';

export const BACKEND_URL = rawBackendUrl.replace(/\/+$/, '');

export const ATE_MT5_API =
  process.env.ATE_MT5_API ||
  `${BACKEND_URL}/api/v1`;

export const ATE_BACKEND_URL = BACKEND_URL;

export const ATE_FRONTEND_URL =
  process.env.ATE_FRONTEND_URL ||
  'https://autonomous-trading-engine.vercel.app';

