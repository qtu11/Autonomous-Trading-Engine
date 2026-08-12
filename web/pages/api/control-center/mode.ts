import type { NextApiRequest, NextApiResponse } from 'next';
import { authedProxy } from '@/lib/middleware/proxy';
export default function handler(req: NextApiRequest, res: NextApiResponse) {
  // BUG FIX: path trước đây có đuôi '.ts' (giống lỗi mt5-login.ts) -> proxy gọi
  // backend /api/control-center/mode.ts -> 404. Bỏ đuôi để khớp endpoint backend.
  return authedProxy(req as any, res, { method: 'POST', path: '/api/control-center/mode', requireAdmin: true });
}
