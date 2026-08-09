import type { NextApiRequest, NextApiResponse } from 'next';
import { proxyToBackend } from '../../../../../../lib/rawFetch';

export const config = {
  api: {
    bodyParser: false,
  },
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const commandId = req.query.id as string;
  await proxyToBackend(req, res, `/api/v1/bridge/commands/${commandId}/receipt`);
}
