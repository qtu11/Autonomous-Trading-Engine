const BACKEND_URL = process.env.ATE_BACKEND_URL || 'http://113.173.192.226:8848';

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { email, password } = req.body;

    const response = await fetch(`${BACKEND_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    // Copy cookies from backend
    const setCookie = response.headers.get('set-cookie');
    if (setCookie) {
      res.setHeader('set-cookie', setCookie);
    }

    return res.status(response.status).json(data);
  } catch (error) {
    console.error('Auth proxy error:', error);
    return res.status(502).json({
      error: 'Backend unavailable',
      details: error instanceof Error ? error.message : 'Unknown error'
    });
  }
}
