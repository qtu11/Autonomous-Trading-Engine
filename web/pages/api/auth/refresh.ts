import type { NextApiRequest, NextApiResponse } from 'next';
import { issueTokens, verifyRefreshToken } from '@/lib/middleware/auth';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Try cookie first, fallback to body
    let refreshToken = '';
    const cookieHeader = req.headers.cookie || '';
    const match = cookieHeader.match(/refresh_token=([^;]+)/);
    if (match) {
      refreshToken = match[1];
    } else if (req.body?.refresh_token) {
      refreshToken = req.body.refresh_token;
    }

    if (!refreshToken) {
      return res.status(401).json({ error: 'No refresh token' });
    }

    const payload = verifyRefreshToken(refreshToken);
    if (!payload) {
      return res.status(401).json({ error: 'Invalid or expired refresh token' });
    }

    // Rotate: issue new pair
    const { accessToken, refreshToken: newRefresh } = issueTokens({
      sub: payload.sub,
      login: payload.login,
      role: payload.role,
    });

    res.setHeader('Set-Cookie', [
      `refresh_token=${newRefresh}; HttpOnly; ${process.env.NODE_ENV === 'production' ? 'Secure;' : ''} SameSite=Strict; Path=/; Max-Age=604800`,
      `access_token=${accessToken}; HttpOnly; ${process.env.NODE_ENV === 'production' ? 'Secure;' : ''} SameSite=Strict; Path=/; Max-Age=900`,
    ]);

    return res.status(200).json({
      status: 'SUCCESS',
      access_token: accessToken,
      refresh_token: newRefresh,
      expires_in: 900,
    });
  } catch {
    return res.status(500).json({ error: 'Internal error' });
  }
}
