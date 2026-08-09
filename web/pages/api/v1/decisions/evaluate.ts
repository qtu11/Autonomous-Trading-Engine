import type { NextApiRequest, NextApiResponse } from 'next';
import { proxyToBackend } from '../../../../../lib/rawFetch';

export const config = {
  api: {
    bodyParser: false,
  },
};

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  await proxyToBackend(req, res, '/api/v1/decisions/evaluate');
}
