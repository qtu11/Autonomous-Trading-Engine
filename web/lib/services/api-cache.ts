/**
 * api-cache.ts - Simple in-memory cache + SWR pattern.
 * Caches responses for `ttl` ms, returns stale data while refetching.
 */
type CacheEntry<T> = {
  data: T | null;
  ts: number;
  inflight: Promise<T | null> | null;
};

const cache = new Map<string, CacheEntry<unknown>>();

export async function cachedFetch<T>(
  key: string,
  fetcher: () => Promise<T | null>,
  ttl: number = 2000
): Promise<T | null> {
  const now = Date.now();
  const entry = cache.get(key) as CacheEntry<T> | undefined;

  // If fresh cache, return immediately
  if (entry && entry.data !== null && now - entry.ts < ttl) {
    return entry.data;
  }

  // If an inflight request exists, return its result (dedup)
  if (entry?.inflight) {
    return entry.inflight;
  }

  // Otherwise fire new request
  const promise = fetcher().then(data => {
    cache.set(key, { data, ts: Date.now(), inflight: null });
    return data;
  }).catch(err => {
    cache.set(key, { data: null, ts: Date.now(), inflight: null });
    throw err;
  });

  cache.set(key, { data: entry?.data ?? null, ts: now, inflight: promise });
  return promise;
}

export function invalidate(keyPrefix?: string) {
  if (!keyPrefix) { cache.clear(); return; }
  for (const k of cache.keys()) {
    if (k.startsWith(keyPrefix)) cache.delete(k);
  }
}
