import type { NextApiRequest, NextApiResponse } from 'next';
import { BACKEND_URL } from '@/lib/api-config';

/**
 * BUG FIX: EA gọi GET /api/v1/economic-calendar/protection (bridge token).
 * Forward thẳng Authorization header của EA tới backend.
 */
export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).end();
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);

  try {
    const url = new URL(`${BACKEND_URL}/api/economic-calendar/protection`);
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

    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': (req.headers.authorization as string) || '',
      },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    const data = await response.json().catch(() => ({ raw: 'ok' }));
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

