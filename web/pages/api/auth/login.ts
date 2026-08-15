import type { NextApiRequest, NextApiResponse } from 'next';
import { issueTokens } from '@/lib/middleware/auth';
import { rateLimit } from '@/lib/middleware/rate-limit';

// BUG FIX (SECURITY): thiếu JWT_SECRET → từ chối login fail-closed với 503 rõ
// ràng (không fallback secret hardcode).
const HAS_JWT_SECRET = !!(process.env.JWT_SECRET && process.env.JWT_REFRESH_SECRET);

// BUG FIX (SECURITY): trước đây có default hardcode (qtusdev07/20022007@Tu) và
// điều kiện login cực lỏng (bất kỳ username nào + password = bridge token là
// vào được). Giờ fail-closed: BẮT BUỘC ADMIN_LOGIN/ADMIN_PASSWORD từ env,
// khớp chính xác cả hai.
const ADMIN_LOGIN = (process.env.ADMIN_LOGIN || '').trim();
const ADMIN_PASSWORD = (process.env.ADMIN_PASSWORD || '').trim();

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // Rate limit login (15 attempts per 15 minutes per IP)
  const ip = (req.headers['x-forwarded-for'] as string || req.socket.remoteAddress || 'unknown').split(',')[0].trim();
  const limit = rateLimit(`login:${ip}`, 15, 15 * 60 * 1000);
  if (!limit.allowed) {
    res.setHeader('Retry-After', String(limit.retryAfter));
    return res.status(429).json({ error: 'Too many attempts', retry_after: limit.retryAfter });
  }

  try {
    const { login, password } = req.body || {};
    if (!login || !password) {
      return res.status(400).json({ error: 'login and password required' });
    }

    const trimmedLogin = String(login).trim();
    const trimmedPass = String(password).trim();

    // Fail-closed: đúng username + đúng password, không có đường tắt nào khác.
    if (!ADMIN_LOGIN || !ADMIN_PASSWORD) {
      return res.status(503).json({ error: 'Authentication not configured (ADMIN_LOGIN/ADMIN_PASSWORD)' });
    }

    // Fail-closed (SECURITY): thiếu JWT secret → không thể cấp token an toàn.
    if (!HAS_JWT_SECRET) {
      return res.status(503).json({ error: 'JWT_SECRET/JWT_REFRESH_SECRET chưa được cấu hình — set trong env (openssl rand -hex 32)' });
    }

    if (trimmedLogin !== ADMIN_LOGIN || trimmedPass !== ADMIN_PASSWORD) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const effectiveUser = trimmedLogin.includes('@') ? trimmedLogin : ADMIN_LOGIN;

    const { accessToken, refreshToken } = issueTokens({
      sub: 'admin',
      login: effectiveUser,
      role: 'admin',
    });

    const isProd = process.env.NODE_ENV === 'production';
    const cookieFlags = `Path=/; Max-Age=2592000; SameSite=Lax${isProd ? '; Secure' : ''}`;

    res.setHeader('Set-Cookie', [
      `refresh_token=${refreshToken}; HttpOnly; ${cookieFlags}`,
      `access_token=${accessToken}; ${cookieFlags}`,
      `quantai_auth=${accessToken}; ${cookieFlags}`,
    ]);

    return res.status(200).json({
      status: 'SUCCESS',
      access_token: accessToken,
      token: accessToken,
      refresh_token: refreshToken,
      expires_in: 86400,
      user: { id: 'admin', login: effectiveUser, role: 'admin' },
    });
  } catch {
    return res.status(500).json({ error: 'Internal error' });
  }
}

