import type { NextApiRequest, NextApiResponse } from 'next';
import { BACKEND_URL } from '@/lib/api-config';

/**
 * BUG FIX: EA gọi GET /api/v1/economic-calendar/protection (bridge token).
 * Route cũ /api/economic-calendar/protection dùng authedProxy -> yêu cầu web JWT
 * -> EA bị 401 "Invalid or expired token" -> news protection fallback "allow
 * entries" (AI có thể trade vào tin). Route v1 này là proxy MỞ (giống
 * v1/telemetry.ts): forward thẳng Authorization header của EA tới backend.
 */
export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).end();
  }

  try {
    const url = new URL(`${BACKEND_URL}/api/economic-calendar/protection`);
    Object.entries(req.query).forEach(([key, value]) => {
      if (value === undefined || value === null) return;
      url.searchParams.append(key, String(value));
    });

    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': (req.headers.authorization as string) || '',
      },
    });

    const data = await response.json().catch(() => ({ raw: 'ok' }));
    return res.status(response.status).json(data);
  } catch (error) {
    return res.status(502).json({
      error: 'Backend unavailable',
      details: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}
