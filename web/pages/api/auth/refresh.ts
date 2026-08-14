import type { NextApiRequest, NextApiResponse } from 'next';
import { issueTokens, verifyRefreshToken, verifyToken } from '@/lib/middleware/auth';


export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Try cookie first, fallback to auth header, then body
    let refreshToken = '';
    const cookieHeader = req.headers.cookie || '';
    const matchRef = cookieHeader.match(/refresh_token=([^;]+)/);
    const matchAcc = cookieHeader.match(/access_token=([^;]+)/);
    const matchAuth = cookieHeader.match(/quantai_auth=([^;]+)/);

    if (matchRef) {
      refreshToken = matchRef[1];
    } else if (matchAcc) {
      refreshToken = matchAcc[1];
    } else if (matchAuth) {
      refreshToken = matchAuth[1];
    } else if (req.headers.authorization?.startsWith('Bearer ')) {
      refreshToken = req.headers.authorization.slice(7).trim();
    } else if (req.body?.refresh_token) {
      refreshToken = req.body.refresh_token;
    }

    if (!refreshToken) {
      return res.status(401).json({ error: 'No refresh token' });
    }

    const payload = verifyRefreshToken(refreshToken) || verifyToken(refreshToken);
    if (!payload) {
      return res.status(401).json({ error: 'Invalid or expired refresh token' });
    }

    // Rotate: issue new pair
    const { accessToken, refreshToken: newRefresh } = issueTokens({
      sub: payload.sub || 'admin',
      login: payload.login || 'qtusdev@quanttrading.ai',
      role: payload.role || 'admin',
    });

    const isProd = process.env.NODE_ENV === 'production';
    const cookieFlags = `Path=/; Max-Age=2592000; SameSite=Lax${isProd ? '; Secure' : ''}`;

    res.setHeader('Set-Cookie', [
      `refresh_token=${newRefresh}; HttpOnly; ${cookieFlags}`,
      `access_token=${accessToken}; ${cookieFlags}`,
      `quantai_auth=${accessToken}; ${cookieFlags}`,
    ]);

    return res.status(200).json({
      status: 'SUCCESS',
      access_token: accessToken,
      token: accessToken,
      refresh_token: newRefresh,
      expires_in: 86400,
    });
  } catch {
    return res.status(500).json({ error: 'Internal error' });
  }
}

