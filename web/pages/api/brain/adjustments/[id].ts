import { BACKEND_URL } from '../../../lib/api-config';
import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'PATCH') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Replace [id] or {id} with actual id from query
    let path = '/api/brain/adjustments/[id]';
    if (req.query.id) {
      path = path.replace('[id]', req.query.id as string).replace('{id}', req.query.id as string);
    }

    const response = await fetch(BACKEND_URL + path, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': (req.headers.authorization as string) || '',
      },
      body: JSON.stringify(req.body),
    });

    const data = await response.json();
    return res.status(response.status).json(data);
  } catch (error) {
    console.error('API error:', error);
    return res.status(502).json({
      error: 'Backend unavailable',
      details: error instanceof Error ? error.message : 'Unknown error'
    });
  }
}