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
    // Collect raw body from Node.js IncomingMessage
    const chunks: Buffer[] = [];
    for await (const chunk of req.body as AsyncIterable<Buffer>) {
      chunks.push(chunk);
    }
    const rawBody = Buffer.concat(chunks).toString('utf8');

    const response = await fetch(`${BACKEND_URL}/api/v1/telemetry`, {
      method: 'POST',
      headers: {
        'Content-Type': (req.headers['content-type'] as string) || 'application/json',
        'Authorization': (req.headers.authorization as string) || '',
      },
      body: rawBody,
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
