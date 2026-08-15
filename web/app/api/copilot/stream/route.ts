// =====================================================================
// AI Copilot streaming endpoint (Server-Sent Events)
// next.config.ts rewrites ALL /api/* to backend, but SSE requires
// special handling (no buffering, proper headers) so this route stays.
// =====================================================================

import { NextRequest } from 'next/server';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// BUG FIX (SECURITY): endpoint /api/copilot/stream giờ yêu cầu bridge token
// (backend đã chặn public) — SSE route phải forward Authorization, không được
// gửi rỗng như trước (trước đây stream public nên không cần).
const bridgeToken = (
  process.env.QUANTAI_BRIDGE_TOKEN ||
  process.env.ATE_BRIDGE_TOKEN ||
  process.env.MT5_BRIDGE_TOKEN ||
  ''
);

const BACKEND_URL = (
  process.env.ATE_BACKEND_URL || 'http://127.0.0.1:8005'
).replace(/\/+$/, '');

export async function GET(req: NextRequest) {
  const url = `${BACKEND_URL}/api/copilot/stream`;

  // Forward all query params (e.g. ?limit=50 for log endpoint)
  const qs = req.nextUrl.search || '';
  const target = url + qs;

  try {
    const upstream = await fetch(target, {
      method: 'GET',
      headers: {
        'Accept': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Authorization': bridgeToken ? `Bearer ${bridgeToken}` : '',
      },
      cache: 'no-store',
    });

    if (!upstream.ok || !upstream.body) {
      return new Response(
        JSON.stringify({ error: 'UPSTREAM_ERROR', status: upstream.status }),
        { status: upstream.status, headers: { 'Content-Type': 'application/json' } }
      );
    }

    return new Response(upstream.body, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });
  } catch (err: any) {
    return new Response(
      JSON.stringify({ error: 'PROXY_ERROR', message: err?.message || 'unknown' }),
      { status: 502, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

export async function POST(req: NextRequest) {
  // Some clients POST to /api/copilot/stream as a non-streaming chat fallback
  const body = await req.text();
  try {
    const upstream = await fetch(`${BACKEND_URL}/api/copilot/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': req.headers.get('content-type') || 'application/json',
        // BUG FIX (SECURITY): không forward Authorization tuỳ ý từ client xuống
        // backend — backend validate token nghiêm ngặt nên dùng bridge token nội bộ.
        'Authorization': bridgeToken ? `Bearer ${bridgeToken}` : '',
      },
      body,
    });
    const responseBody = await upstream.text();
    return new Response(responseBody, {
      status: upstream.status,
      headers: { 'Content-Type': 'application/json' },
    });
  } catch (err: any) {
    return new Response(
      JSON.stringify({ error: 'PROXY_ERROR', message: err?.message || 'unknown' }),
      { status: 502, headers: { 'Content-Type': 'application/json' } }
    );
  }
}