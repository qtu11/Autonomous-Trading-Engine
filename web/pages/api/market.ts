import { BACKEND_URL } from './lib/api-config';
import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { query } = req;
    const params = new URLSearchParams();

    // Copy query params
    Object.entries(query).forEach(([key, value]) => {
      if (key !== '_next' && value !== undefined && value !== null) {
        params.append(key, String(value));
      }
    });

    // Default to 2000 candles if not specified
    if (!params.has('count')) {
      params.append('count', '2000');
    }

    // Build URL
    let path = '/api/market';
    if (req.query.id) {
      path = path.replace('[id]', req.query.id as string).replace('{id}', req.query.id as string);
    }

    const url = BACKEND_URL + path + (params.toString() ? '?' + params.toString() : '');

    console.log('[Market API] Fetching:', url);

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': (req.headers.authorization as string) || '',
      },
    });

    const data = await response.json();

    // Log candle count for debugging
    if (data.candles) {
      console.log(`[Market API] Received ${data.candles.length} candles`);
    }

    return res.status(response.status).json(data);
  } catch (error) {
    console.error('API error:', error);
    return res.status(502).json({
      error: 'Backend unavailable',
      details: error instanceof Error ? error.message : 'Unknown error'
    });
  }
}
