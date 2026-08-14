import { useEffect, useRef, useCallback } from 'react';

/**
 * useFetchInterval - Custom hook to prevent memory leak from overlapping intervals.
 * Properly:
 *  - Cancels in-flight requests via AbortController on each tick
 *  - Clears interval on unmount
 *  - Pauses on visibility hidden
 *  - Resets delay on deps change
 */
export function useFetchInterval<T>(
  fetcher: (signal: AbortSignal) => Promise<T | null>,
  delay: number,
  deps: any[] = [],
  onData?: (data: T | null) => void,
  enabled: boolean = true
) {
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const onDataRef = useRef(onData);
  onDataRef.current = onData;
  const abortRef = useRef<AbortController | null>(null);

  const run = useCallback(async () => {
    if (!enabled) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const data = await fetcherRef.current(controller.signal);
      if (!controller.signal.aborted) {
        onDataRef.current?.(data);
      }
    } catch (err) {
      // AbortError is expected on cancel; swallow it
      if (err instanceof DOMException && err.name === 'AbortError') return;
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      abortRef.current?.abort();
      return;
    }

    let intervalId: ReturnType<typeof setInterval> | null = null;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    const start = () => {
      run();
      intervalId = setInterval(run, delay);
    };

    const stop = () => {
      if (intervalId) clearInterval(intervalId);
      if (timeoutId) clearTimeout(timeoutId);
      intervalId = null;
      timeoutId = null;
    };

    const handleVisibility = () => {
      if (document.hidden) {
        stop();
      } else {
        start();
      }
    };

    start();
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      stop();
      document.removeEventListener('visibilitychange', handleVisibility);
      abortRef.current?.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [delay, run, enabled, ...deps]);
}

