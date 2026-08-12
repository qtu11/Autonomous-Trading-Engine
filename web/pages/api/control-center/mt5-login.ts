import type { NextApiRequest, NextApiResponse } from 'next';
import { authedProxy } from '@/lib/middleware/proxy';

// BUG FIX: trước đây path = '/api/control-center/mt5-login.ts' — có đuôi .ts và
// sai route → backend trả 404. Route đúng là /api/control-center/login-mt5.
export default function handler(req: NextApiRequest, res: NextApiResponse) {
  return authedProxy(req as any, res, { method: 'POST', path: '/api/control-center/login-mt5', requireAdmin: true });
}
