import type { NextApiRequest, NextApiResponse } from 'next';
const BACKEND_URL = process.env.ATE_BACKEND_URL || 'http://127.0.0.1:8005';
export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') { return res.status(405).end(); }
  try {
    const body = JSON.stringify(req.body);
    const response = await fetch(`${BACKEND_URL}/api/v1/bridge/calendar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': (req.headers.authorization as string) || '' },
      body,
    });
    const data = await response.json().catch(() => ({ raw: 'ok' }));
    return res.status(response.status).json(data);
  } catch (error) {
    return res.status(502).json({ error: 'Backend unavailable', details: error instanceof Error ? error.message : 'Unknown error' });
  }
}
