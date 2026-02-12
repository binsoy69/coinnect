import { useState, useEffect, useCallback } from "react";
import { API_BASE } from "../constants/api";
import { useWebSocket } from "../context/WebSocketContext";

/**
 * Hook for subscribing to machine status.
 *
 * Fetches initial status from REST API, then subscribes to
 * real-time STATE_CHANGE events via WebSocket.
 */
export function useMachineStatus() {
  const { subscribe, unsubscribe, isConnected } = useWebSocket();
  const [status, setStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Initial fetch
  const fetchStatus = useCallback(async () => {
    try {
      const resp = await fetch(`${API_BASE}/status`);
      if (resp.ok) {
        const data = await resp.json();
        setStatus(data);
      }
    } catch {
      // Will retry on next WS reconnect
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Re-fetch when WS reconnects
  useEffect(() => {
    if (isConnected) {
      fetchStatus();
    }
  }, [isConnected, fetchStatus]);

  // Subscribe to state changes
  useEffect(() => {
    const handler = (event) => {
      if (event.payload) {
        setStatus((prev) => (prev ? { ...prev, ...event.payload } : event.payload));
      }
    };
    subscribe("STATE_CHANGE", handler);
    return () => unsubscribe("STATE_CHANGE", handler);
  }, [subscribe, unsubscribe]);

  const isReady =
    status?.bill_device?.connection === "connected" &&
    status?.coin_device?.connection === "connected";

  return { status, isLoading, isReady };
}
