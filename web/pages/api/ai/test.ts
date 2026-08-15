import type { NextApiRequest, NextApiResponse } from 'next';
import { authedProxy } from '@/lib/middleware/proxy';

// BUG FIX: api.ts testAIConnection() gọi /api/ai/test nhưng pages/api/ai/ rỗng
// → rewrite catch-all gửi JWT user xuống backend (strict auth) → 401.
export default function handler(req: NextApiRequest, res: NextApiResponse) {
  return authedProxy(req as any, res, { method: 'POST', path: '/api/ai/test', requireAdmin: true });
}
