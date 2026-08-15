import type { NextApiRequest, NextApiResponse } from 'next';
import { authedProxy } from '@/lib/middleware/proxy';

// BUG FIX: trước đây forward nguyên Authorization (JWT user) xuống backend —
// backend giờ validate token nghiêm ngặt nên JWT bị 401. Dùng authedProxy:
// xác thực JWT cục bộ, forward bridge token xuống backend.
export default function handler(req: NextApiRequest, res: NextApiResponse) {
  return authedProxy(req as any, res, { method: 'POST', path: '/api/news/analyze' });
}
