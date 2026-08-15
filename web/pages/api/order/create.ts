import type { NextApiRequest, NextApiResponse } from 'next';
import { authedProxy } from '@/lib/middleware/proxy';

// BUG FIX: /api/order/create được UI (QuickTradePanel) gọi trực tiếp nhưng
// không có proxy file → rơi vào rewrite catch-all → backend nhận JWT của user
// → backend (strict auth) từ chối. Proxy này xác thực JWT cục bộ rồi forward
// bridge token xuống backend.
export default function handler(req: NextApiRequest, res: NextApiResponse) {
  return authedProxy(req as any, res, { method: 'POST', path: '/api/order/create', requireAdmin: true });
}
