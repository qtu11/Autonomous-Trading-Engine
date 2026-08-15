import type { NextApiRequest, NextApiResponse } from 'next';
import { authedProxy } from '@/lib/middleware/proxy';

// BUG FIX: ControlCenter gọi fetchMT5Diagnostics() → /api/control-center/mt5-diagnostics
// nhưng không có proxy file → rewrite catch-all gửi JWT user xuống backend (strict
// auth) → 401. Thêm proxy để xác thực JWT cục bộ + forward bridge token.
export default function handler(req: NextApiRequest, res: NextApiResponse) {
  return authedProxy(req as any, res, { method: 'GET', path: '/api/control-center/mt5-diagnostics' });
}
