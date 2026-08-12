/**
 * rate-limit.ts - In-memory rate limiter.
 * For single-instance Next.js. For multi-instance, use Redis.
 */

interface LimitEntry {
  count: number;
  resetAt: number;
}

const buckets = new Map<string, LimitEntry>();

export function rateLimit(
  key: string,
  max: number,
  windowMs: number
): { allowed: boolean; remaining: number; retryAfter: number } {
  const now = Date.now();
  const entry = buckets.get(key);

  if (!entry || entry.resetAt < now) {
    buckets.set(key, { count: 1, resetAt: now + windowMs });
    return { allowed: true, remaining: max - 1, retryAfter: 0 };
  }

  if (entry.count >= max) {
    return {
      allowed: false,
      remaining: 0,
      retryAfter: Math.ceil((entry.resetAt - now) / 1000),
    };
  }

  entry.count++;
  return {
    allowed: true,
    remaining: max - entry.count,
    retryAfter: 0,
  };
}
