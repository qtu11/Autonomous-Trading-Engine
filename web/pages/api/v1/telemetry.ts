import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.ATE_BACKEND_URL || 'http://113.173.192.226:8848';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Forward MT5 telemetry to backend — use raw body buffer to avoid JSON parsing issues
    const response = await fetch(`${BACKEND_URL}/api/v1/telemetry`, {
      method: 'POST',
      headers: {
        'Content-Type': req.headers['content-type'] as string || 'application/json',
        'Authorization': (req.headers.authorization as string) || '',
      },
      body: req.body,
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
