import type { NextApiRequest, NextApiResponse } from 'next';
import { BACKEND_URL } from '@/lib/api-config';
import { requireAuth, requireAdmin, type AuthRequest } from './auth';

/**
 * Bridge token used to authenticate this Next.js instance against the FastAPI
 * backend. The backend validates tokens strictly (fail-closed), so the web
 * layer MUST forward a valid bridge token — never the user's JWT.
 */
// BUG FIX (SECURITY): trước đây fallback về token mặc định '20022007@Tu' đã
// public trong git history/docs — nếu deploy mà quên set env, toàn bộ hệ thống
// chạy với token ai cũng biết. Giờ fail-closed: trả chuỗi rỗng → backend trả 401
// rõ ràng thay vì âm thầm dùng token công khai.
function bridgeToken(): string {
  return (
    process.env.QUANTAI_BRIDGE_TOKEN ||
    process.env.ATE_BRIDGE_TOKEN ||
    process.env.MT5_BRIDGE_TOKEN ||
    ''
  );
}

function buildUrl(req: NextApiRequest, targetPath: string): URL {
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
  return url;
}

/**
 * Authenticated proxy helper.
 * Validates Bearer token locally (no extra round-trip to backend).
 * Then forwards the request to the FastAPI backend using the bridge token.
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
  // Auth check (user session)
  const user = options.requireAdmin
    ? requireAdmin(req, res)
    : requireAuth(req, res);
  if (!user) return;

  const method = options.method || req.method || 'GET';
  const targetPath = options.path.startsWith('/') ? options.path : `/${options.path}`;
  const url = buildUrl(req, targetPath);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);

  try {
    // BUG FIX (SECURITY): user đã xác thực cục bộ bằng JWT; gửi xuống backend
    // phải là bridge token (backend validate token nghiêm ngặt, không nhận JWT).
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${bridgeToken()}`,
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

    let response: Response;
    try {
      response = await fetch(url.toString(), init);
    } catch (fetchErr: any) {
      // Automatic Fallback: if WAN/DNS failed and target was not loopback,
      // fall back to the local backend (standard dev port 8005).
      if (!url.hostname.includes('127.0.0.1') && !url.hostname.includes('localhost')) {
        const fallbackUrl = new URL(`http://127.0.0.1:8005${targetPath}`);
        url.searchParams.forEach((val, k) => fallbackUrl.searchParams.append(k, val));
        response = await fetch(fallbackUrl.toString(), init);
      } else {
        throw fetchErr;
      }
    }
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

/**
 * Public proxy helper for read-only market data, status, charts, and telemetry.
 * Always injects the internal bridge token so the backend (strict auth) accepts.
 */
export async function publicProxy(
  req: NextApiRequest,
  res: NextApiResponse,
  options: {
    method?: string;
    path: string;
  }
) {
  const method = options.method || req.method || 'GET';
  const targetPath = options.path.startsWith('/') ? options.path : `/${options.path}`;
  const url = buildUrl(req, targetPath);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);

  try {
    // BUG FIX (SECURITY): luôn dùng bridge token nội bộ — không chuyển token
    // tuỳ ý từ client xuống backend (backend giờ validate token nghiêm ngặt).
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${bridgeToken()}`,
    };

    const init: RequestInit = {
      method,
      headers,
      signal: controller.signal,
    };

    if (method !== 'GET' && method !== 'HEAD' && req.body !== undefined && req.body !== null) {
      init.body = typeof req.body === 'string' ? req.body : JSON.stringify(req.body);
    }

    let response: Response;
    try {
      response = await fetch(url.toString(), init);
    } catch (fetchErr: any) {
      if (!url.hostname.includes('127.0.0.1') && !url.hostname.includes('localhost')) {
        const fallbackUrl = new URL(`http://127.0.0.1:8005${targetPath}`);
        url.searchParams.forEach((val, k) => fallbackUrl.searchParams.append(k, val));
        response = await fetch(fallbackUrl.toString(), init);
      } else {
        throw fetchErr;
      }
    }
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
    return res.status(502).json({
      error: 'Backend unavailable',
      details: error?.message || 'Unknown error',
      backend_target: BACKEND_URL,
    });
  }
}
