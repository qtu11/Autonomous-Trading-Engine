import { BACKEND_URL } from '@/lib/api-config';
import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const params = new URLSearchParams();
    Object.entries(req.query).forEach(([k, v]) => {
      if (v !== undefined && v !== null) params.append(k, String(v));
    });
    const url = BACKEND_URL + '/api/patterns' + (params.toString() ? '?' + params.toString() : '');

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': (req.headers.authorization as string) || '',
      },
    });

    const data = await response.json();
    return res.status(response.status).json(data);
  } catch (error) {
    console.error('Patterns API error:', error);
    return res.status(502).json({ error: 'Backend unavailable', details: error instanceof Error ? error.message : 'Unknown error' });
  }
}
