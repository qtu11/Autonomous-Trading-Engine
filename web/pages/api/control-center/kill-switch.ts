import type { NextApiRequest, NextApiResponse } from 'next';
import { authedProxy } from '@/lib/middleware/proxy';
export default function handler(req: NextApiRequest, res: NextApiResponse) {
  // BUG FIX: bỏ đuôi '.ts' khỏi path proxy -> khớp endpoint backend (404 trước đây)
  return authedProxy(req as any, res, { method: 'POST', path: '/api/control-center/kill-switch', requireAdmin: true });
}
