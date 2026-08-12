import type { NextApiRequest, NextApiResponse } from 'next';
import { authedProxy } from '@/lib/middleware/proxy';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  return authedProxy(req as any, res, { path: '/api/control-center/settings', requireAdmin: true });
}
