const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

const HTTPS_PORT = 8443;
const BACKEND_PORT = 8005;
const SSL_DIR = path.join(__dirname, 'ssl');

// Create HTTPS server with PFX
const server = https.createServer({
  pfx: fs.readFileSync(path.join(SSL_DIR, 'server.pfx')),
  passphrase: 'password123'
}, (req, res) => {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] ${req.method} ${req.url}`);
  
  const proxyReq = http.request({
    hostname: '127.0.0.1',
    port: BACKEND_PORT,
    path: req.url,
    method: req.method,
    headers: {
      ...req.headers,
      'X-Forwarded-Proto': 'https',
      'X-Forwarded-Host': req.headers.host
    }
  }, (proxyRes) => {
    res.writeHead(proxyRes.statusCode, proxyRes.headers);
    proxyRes.pipe(res);
  });
  
  req.pipe(proxyReq);
  
  proxyReq.on('error', (e) => {
    console.error(`[${timestamp}] Proxy error:`, e.message);
    res.writeHead(502, {'Content-Type': 'application/json'});
    res.end(JSON.stringify({error: 'Backend unavailable', details: e.message}));
  });
});

server.listen(HTTPS_PORT, '0.0.0.0', () => {
  console.log(`========================================`);
  console.log(`HTTPS Proxy Server Started`);
  console.log(`========================================`);
  console.log(`HTTPS Port: ${HTTPS_PORT}`);
  console.log(`Backend:    http://localhost:${BACKEND_PORT}`);
  console.log(`URL:       https://113.173.192.226:${HTTPS_PORT}`);
  console.log(`========================================`);
});

// Handle errors
server.on('error', (e) => {
  console.error('Server error:', e.message);
});
