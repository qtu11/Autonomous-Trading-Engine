import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.ATE_BACKEND_URL || 'http://113.173.192.226:8848';

export const config = {
  api: {
    bodyParser: false,
  },
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).end();
  }

  try {
    // Read raw body using req.read() (Pages Router built-in)
    const rawBody = await req.read() ?? '';

    const response = await fetch(`${BACKEND_URL}/api/v1/telemetry`, {
      method: 'POST',
      headers: {
        'Content-Type': req.headers['content-type'] as string || 'application/json',
        'Authorization': (req.headers.authorization as string) || '',
      },
      body: rawBody instanceof Uint8Array ? Buffer.from(rawBody) : rawBody,
    });

    const text = await response.text();
    try {
      const json = JSON.parse(text);
      return res.status(response.status).json(json);
    } catch {
      return res.status(response.status).send(text);
    }
  } catch (error) {
    return res.status(502).json({
      error: 'Backend unavailable',
      details: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}
