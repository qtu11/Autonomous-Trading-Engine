import type { NextApiRequest, NextApiResponse } from 'next';
import { BACKEND_URL } from '@/lib/api-config';
import { requireAuth, optionalAuth, type AuthRequest } from './auth';

/**
 * PHASE 2: Authenticated proxy helper.
 * Validates Bearer token locally (no extra round-trip to backend).
 * Then forwards the request to the FastAPI backend.
 */
export async function authedProxy(
  req: AuthRequest,
  res: NextApiResponse,
  options: {
    method?: string;
    path: string;
    requireAdmin?: boolean;
  }
) {
  // Auth check
  const user = options.requireAdmin
    ? requireAdminOnly(req, res)
    : requireAuth(req, res);
  if (!user) return;

  const method = options.method || req.method || 'GET';
  const url = new URL(BACKEND_URL + options.path);

  // Forward query params
  Object.entries(req.query).forEach(([key, value]) => {
    if (key === '_next' || value === undefined || value === null) return;
    url.searchParams.append(key, String(value));
  });

  try {
    let authHeader = (req.headers.authorization as string) || '';
    if (!authHeader.startsWith('Bearer ') || authHeader === 'Bearer authenticated') {
      let token = '';
      if (req.headers.cookie) {
        const matchAcc = req.headers.cookie.match(/access_token=([^;]+)/);
        const matchAuth = req.headers.cookie.match(/quantai_auth=([^;]+)/);
        token = matchAcc ? matchAcc[1] : (matchAuth ? matchAuth[1] : '');
      }
      if (token && token !== 'authenticated') {
        authHeader = `Bearer ${token}`;
      } else {
        const bridgeToken = process.env.QUANTAI_BRIDGE_TOKEN || 'openssl_rand_hex_32';
        authHeader = `Bearer ${bridgeToken}`;
      }
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Authorization': authHeader,
      'X-Forwarded-User': user.login,
      'X-User-Role': user.role,
    };


    const init: RequestInit = { method, headers };
    if (method !== 'GET' && method !== 'HEAD' && req.body) {
      init.body = JSON.stringify(req.body);
    }

    const response = await fetch(url.toString(), init);
    const setCookie = response.headers.get('set-cookie');
    if (setCookie) res.setHeader('set-cookie', setCookie);

    const text = await response.text();
    let data: any;
    try { data = JSON.parse(text); } catch { data = { raw: text }; }

    res.status(response.status).json(data);
  } catch (error) {
    res.status(502).json({
      error: 'Backend unavailable',
      details: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}

function requireAdminOnly(req: AuthRequest, res: NextApiResponse) {
  const { requireAdmin } = require('./auth') as any;
  return requireAdmin(req, res);
}

