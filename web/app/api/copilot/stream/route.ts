// FIX LỖI 8: SSE stream endpoint for AI Copilot
// This proxies to the FastAPI backend which generates real-time AI auto-trade events

import { NextRequest } from 'next/server';

export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  const encoder = new TextEncoder();
  
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
  
  const stream = new ReadableStream({
    async start(controller) {
      let lastIdx = 0;
      
      const sendEvent = (data: string) => {
        controller.enqueue(encoder.encode(`data: ${data}\n\n`));
      };
      
      const fetchEvents = async () => {
        try {
          const res = await fetch(`${backendUrl}/api/copilot/log?limit=50`, {
            headers: {
              'Authorization': request.headers.get('Authorization') || '',
            },
            cache: 'no-store',
          });
          
          if (res.ok) {
            const events = await res.json();
            if (Array.isArray(events)) {
              for (let i = lastIdx; i < events.length; i++) {
                sendEvent(JSON.stringify(events[i]));
              }
              lastIdx = events.length;
            }
          }
        } catch {
          // Silent - backend might not be available
        }
      };
      
      // Send heartbeat
      sendEvent(JSON.stringify({
        id: 'heartbeat',
        ts: new Date().toISOString(),
        level: 'INFO',
        action: 'HEARTBEAT',
        symbol: 'XAUUSD',
        details: { message: 'SSE connection active' },
      }));
      
      // Fetch events initially
      await fetchEvents();
      
      // Poll for new events every 2 seconds
      const interval = setInterval(fetchEvents, 2000);
      
      // Cleanup on close
      request.signal.addEventListener('abort', () => {
        clearInterval(interval);
        controller.close();
      });
    },
  });
  
  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}
