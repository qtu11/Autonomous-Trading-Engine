import type { NextApiRequest, NextApiResponse } from 'next';
import { BACKEND_URL } from '@/lib/api-config';
import { requireAuth, requireAdmin, optionalAuth, type AuthRequest } from './auth';

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
    ? requireAdmin(req, res)
    : requireAuth(req, res);
  if (!user) return;


  const method = options.method || req.method || 'GET';
  const targetPath = options.path.startsWith('/') ? options.path : `/${options.path}`;
  const url = new URL(`${BACKEND_URL}${targetPath}`);

  // Forward query params (excluding Next.js internal params)
  Object.entries(req.query).forEach(([key, value]) => {
    if (
      key === '_next' ||
      key === 'slug' ||
      key === 'path' ||
      value === undefined ||
      value === null
    ) return;
    url.searchParams.append(key, String(value));
  });

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);

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
        const bridgeToken = process.env.QUANTAI_BRIDGE_TOKEN || '20022007@Tu';
        authHeader = `Bearer ${bridgeToken}`;
      }
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Authorization': authHeader,
      'X-Forwarded-User': user.login,
      'X-User-Role': user.role,
    };

    const init: RequestInit = {
      method,
      headers,
      signal: controller.signal,
    };

    if (method !== 'GET' && method !== 'HEAD' && req.body !== undefined && req.body !== null) {
      init.body = typeof req.body === 'string' ? req.body : JSON.stringify(req.body);
    }

    const response = await fetch(url.toString(), init);
    clearTimeout(timeoutId);

    const setCookie = response.headers.get('set-cookie');
    if (setCookie) res.setHeader('set-cookie', setCookie);

    const text = await response.text();
    let data: any;
    try {
      data = JSON.parse(text);
    } catch {
      data = { raw: text };
    }

    return res.status(response.status).json(data);
  } catch (error: any) {
    clearTimeout(timeoutId);
    const isAbort = error?.name === 'AbortError';
    return res.status(502).json({
      error: 'Backend unavailable',
      details: isAbort
        ? `Request timed out connecting to ${BACKEND_URL}`
        : error instanceof Error
        ? error.message
        : 'Unknown error',
      backend_target: BACKEND_URL,
    });
  }
}


