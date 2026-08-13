import { BACKEND_URL } from '@/lib/api-config';
import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).end();
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);

  try {
    const body = typeof req.body === 'string' ? req.body : JSON.stringify(req.body);

    const response = await fetch(`${BACKEND_URL}/api/v1/telemetry`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': (req.headers.authorization as string) || '',
      },
      body,
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

