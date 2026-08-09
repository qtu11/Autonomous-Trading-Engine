import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.ATE_BACKEND_URL || 'http://113.173.192.226:8848';

export const config = {
  api: {
    // Disable body parsing — let us forward the raw buffered body
    bodyParser: false,
  },
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).end();
  }

  try {
    // Collect raw body from the Node.js buffered stream
    const chunks: Buffer[] = [];
    const body = req.body as unknown as NodeJS.ReadableStream;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const stream = body as any;
    if (stream && typeof stream.on === 'function') {
      await new Promise<void>((resolve, reject) => {
        stream.on('data', (chunk: Buffer) => chunks.push(chunk));
        stream.on('end', resolve);
        stream.on('error', reject);
      });
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
