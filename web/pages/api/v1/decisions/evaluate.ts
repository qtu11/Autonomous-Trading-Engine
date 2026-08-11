import { BACKEND_URL } from '../../../../lib/api-config';
import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') { return res.status(405).end(); }
  try {
    const body = JSON.stringify(req.body);
    const response = await fetch(`${BACKEND_URL}/api/v1/decisions/evaluate`, {
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
