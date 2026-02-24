import { useRef, useCallback } from 'react';

export function useThrottle<T extends (...args: any[]) => any>(
  func: T,
  delay: number
): T {
  const lastRun = useRef(0);
  const timeout = useRef<NodeJS.Timeout | null>(null);

  return useCallback(
    (...args: any[]) => {
      const now = Date.now();

      if (now - lastRun.current >= delay) {
        func(...args);
        lastRun.current = now;
      } else {
        if (timeout.current) clearTimeout(timeout.current);
        timeout.current = setTimeout(() => {
          func(...args);
          lastRun.current = Date.now();
        }, delay - (now - lastRun.current));
      }
    },
    [func, delay]
  ) as T;
}
