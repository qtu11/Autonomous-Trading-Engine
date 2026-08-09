import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.ATE_BACKEND_URL || 'http://113.173.192.226:8848';

export const config = {
  api: {
    bodyParser: false,
  },
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    res.status(405).end();
    return;
  }

  try {
    const chunks: string[] = [];
    if (req.body) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const stream = req.body as any;
      for await (const chunk of stream) {
        chunks.push(Buffer.from(chunk).toString('utf8'));
      }
    }
    const rawBody = chunks.join('');
    const commandId = req.query.id as string;
    const url = `${BACKEND_URL}/api/v1/bridge/commands/${commandId}/receipt`;

    const response = await fetch(url, {
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
      res.status(response.status).json(json);
    } catch {
      res.status(response.status).send(text);
    }
  } catch (error) {
    res.status(502).json({
      error: 'Backend unavailable',
      details: error instanceof Error ? error.message : 'Unknown error',
    });
  }
}
