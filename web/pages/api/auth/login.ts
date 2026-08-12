import type { NextApiRequest, NextApiResponse } from 'next';
import { issueTokens } from '@/lib/middleware/auth';
import { rateLimit } from '@/lib/middleware/rate-limit';

const ADMIN_LOGIN = process.env.ADMIN_LOGIN || 'qtusdev@quanttrading.ai';
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'qtusdev07';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // PHASE 2: Rate limit login (5 attempts per 15 minutes per IP)
  const ip = (req.headers['x-forwarded-for'] as string || req.socket.remoteAddress || 'unknown').split(',')[0].trim();
  const limit = rateLimit(`login:${ip}`, 5, 15 * 60 * 1000);
  if (!limit.allowed) {
    res.setHeader('Retry-After', String(limit.retryAfter));
    return res.status(429).json({ error: 'Too many attempts', retry_after: limit.retryAfter });
  }

  try {
    const { login, password } = req.body || {};
    if (!login || !password) {
      return res.status(400).json({ error: 'login and password required' });
    }

    if (login !== ADMIN_LOGIN || password !== ADMIN_PASSWORD) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const { accessToken, refreshToken } = issueTokens({
      sub: 'admin',
      login: login,
      role: 'admin',
    });

    res.setHeader('Set-Cookie', [
      `refresh_token=${refreshToken}; HttpOnly; ${process.env.NODE_ENV === 'production' ? 'Secure;' : ''} SameSite=Strict; Path=/; Max-Age=604800`,
      `access_token=${accessToken}; HttpOnly; ${process.env.NODE_ENV === 'production' ? 'Secure;' : ''} SameSite=Strict; Path=/; Max-Age=900`,
    ]);

    return res.status(200).json({
      status: 'SUCCESS',
      access_token: accessToken,
      refresh_token: refreshToken,
      expires_in: 900,
      user: { id: 'admin', login, role: 'admin' },
    });
  } catch {
    return res.status(500).json({ error: 'Internal error' });
  }
}
