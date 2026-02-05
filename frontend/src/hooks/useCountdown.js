import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Custom hook for countdown timer functionality
 * @param {number} initialSeconds - Starting seconds for countdown
 * @param {function} onComplete - Callback when timer reaches 0
 * @param {boolean} autoStart - Whether to start automatically (default: true)
 */
export function useCountdown(initialSeconds, onComplete, autoStart = true) {
  const [seconds, setSeconds] = useState(initialSeconds);
  const [isRunning, setIsRunning] = useState(autoStart);
  const [isComplete, setIsComplete] = useState(false);
  const intervalRef = useRef(null);
  const onCompleteRef = useRef(onComplete);

  // Keep callback ref updated
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  // Main countdown effect
  useEffect(() => {
    if (!isRunning || isComplete) {
      return;
    }

    intervalRef.current = setInterval(() => {
      setSeconds(prev => {
        if (prev <= 1) {
          clearInterval(intervalRef.current);
          setIsRunning(false);
          setIsComplete(true);
          if (onCompleteRef.current) {
            onCompleteRef.current();
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isRunning, isComplete]);

  // Reset timer to initial value
  const reset = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    setSeconds(initialSeconds);
    setIsComplete(false);
    setIsRunning(true);
  }, [initialSeconds]);

  // Pause timer
  const pause = useCallback(() => {
    setIsRunning(false);
  }, []);

  // Resume timer
  const resume = useCallback(() => {
    if (!isComplete) {
      setIsRunning(true);
    }
  }, [isComplete]);

  // Start timer (alias for resume when starting fresh)
  const start = useCallback(() => {
    setIsRunning(true);
  }, []);

  // Stop timer completely
  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    setIsRunning(false);
  }, []);

  // Calculate progress percentage (0-100)
  const progress = Math.max(0, Math.min(100, ((initialSeconds - seconds) / initialSeconds) * 100));

  // Calculate remaining progress (100-0)
  const remainingProgress = 100 - progress;

  return {
    seconds,
    isRunning,
    isComplete,
    progress,
    remainingProgress,
    reset,
    pause,
    resume,
    start,
    stop,
  };
}

export default useCountdown;
