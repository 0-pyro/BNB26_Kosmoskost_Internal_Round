import { useCallback, useEffect, useRef, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseWakeLockReturn {
  isLocked: boolean;
  request: () => Promise<void>;
  release: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Screen Wake Lock — prevents the screen from turning off during a session.
 * Uses navigator.wakeLock.request('screen').
 *
 * Automatically re-acquires the lock when the page becomes visible again
 * (e.g., after tab switch or screen lock/unlock cycle).
 */
export function useWakeLock(): UseWakeLockReturn {
  const [isLocked, setIsLocked] = useState(false);
  const sentinelRef = useRef<WakeLockSentinel | null>(null);
  const wantLockRef = useRef(false);

  const acquireLock = useCallback(async () => {
    if (!("wakeLock" in navigator)) {
      console.warn("[wakelock] Wake Lock API not supported");
      return;
    }
    try {
      const sentinel = await navigator.wakeLock.request("screen");
      sentinelRef.current = sentinel;
      setIsLocked(true);

      sentinel.addEventListener("release", () => {
        sentinelRef.current = null;
        setIsLocked(false);
      });
    } catch (err) {
      console.warn("[wakelock] Failed to acquire", err);
      setIsLocked(false);
    }
  }, []);

  const request = useCallback(async () => {
    wantLockRef.current = true;
    await acquireLock();
  }, [acquireLock]);

  const release = useCallback(async () => {
    wantLockRef.current = false;
    if (sentinelRef.current) {
      await sentinelRef.current.release();
      sentinelRef.current = null;
      setIsLocked(false);
    }
  }, []);

  // Re-acquire on visibility change (lock is auto-released when tab hidden)
  useEffect(() => {
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible" && wantLockRef.current) {
        acquireLock();
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [acquireLock]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (sentinelRef.current) {
        sentinelRef.current.release();
      }
    };
  }, []);

  return { isLocked, request, release };
}
