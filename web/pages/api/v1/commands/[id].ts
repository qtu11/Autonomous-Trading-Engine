import type { NextApiRequest, NextApiResponse } from 'next';
import { authedProxy } from '@/lib/middleware/proxy';
export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const id = (req.query.id as string) || '';
  return authedProxy(req as any, res, { method: 'GET', path: `/api/v1/commands/${id}` });
}
