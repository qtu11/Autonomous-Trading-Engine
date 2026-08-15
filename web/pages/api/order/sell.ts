import type { NextApiRequest, NextApiResponse } from 'next';
import { authedProxy } from '@/lib/middleware/proxy';

// BUG FIX: backend không có route /api/order/sell (chỉ có /api/order/create với
// body {direction, quantity, stop_loss, take_profit}) — proxy cũ gọi thẳng → 404.
export default function handler(req: NextApiRequest, res: NextApiResponse) {
  return authedProxy(req as any, res, { method: 'POST', path: '/api/order/create', requireAdmin: true });
}
