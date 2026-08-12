/**
 * time.ts - Single source of truth for timestamp parsing.
 * Handles: ISO string, Unix seconds, Unix milliseconds, Date.
 * Always returns Unix SECONDS (lightweight-charts v5 expects seconds).
 */
export function parseCandleTime(raw: unknown): number {
  if (typeof raw === 'number') {
    // If too large, treat as ms; else seconds.
    return raw > 1e12 ? Math.floor(raw / 1000) : Math.floor(raw);
  }
  if (typeof raw === 'string') {
    const s = raw.trim();
    if (!s) return Math.floor(Date.now() / 1000);
    // Try ISO parse
    const d = new Date(s);
    if (!isNaN(d.getTime())) {
      return Math.floor(d.getTime() / 1000);
    }
    // Try numeric string
    const num = Number(s);
    if (!isNaN(num)) {
      return num > 1e12 ? Math.floor(num / 1000) : Math.floor(num);
    }
  }
  // Fallback: now
  return Math.floor(Date.now() / 1000);
}

export function isoToSeconds(iso: string): number {
  return parseCandleTime(iso);
}

export function secondsToIso(sec: number): string {
  return new Date(sec * 1000).toISOString();
}

export function formatTimeVN(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}
