import type { NextApiRequest, NextApiResponse } from 'next';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  res.setHeader('Set-Cookie', [
    'refresh_token=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0',
    'access_token=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0',
  ]);
  res.status(200).json({ status: 'SUCCESS' });
}
