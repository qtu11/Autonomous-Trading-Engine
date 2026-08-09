/**
 * Raw fetch utility for MT5 bridge endpoints.
 * Disables bodyParser so we forward the raw request body to backend.
 */
import type { NextApiRequest, NextApiResponse } from 'next';

const BACKEND_URL = process.env.ATE_BACKEND_URL || 'http://113.173.192.226:8848';

export const config = {
  api: {
    bodyParser: false,
  },
};

export async function readRawBody(req: NextApiRequest): Promise<string> {
  if (!req.body) return '';
  const chunks: string[] = [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const stream = req.body as AsyncIterable<Buffer>;
  for await (const chunk of stream) {
    chunks.push(Buffer.from(chunk).toString('utf8'));
  }
  return chunks.join('');
}

export async function proxyToBackend(
  req: NextApiRequest,
  res: NextApiResponse,
  backendPath: string,
): Promise<void> {
  if (req.method !== 'POST') {
    res.status(405).end();
    return;
  }

  try {
    const rawBody = await readRawBody(req);

    const response = await fetch(`${BACKEND_URL}${backendPath}`, {
      method: 'POST',
      headers: {
        'Content-Type': req.headers['content-type'] as string || 'application/json',
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
