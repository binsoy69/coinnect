import { useState, useEffect } from "react";
import { API_BASE } from "../constants/api";
import { useWebSocket } from "../context/WebSocketContext";

/**
 * Hook to manage physical bill acceptance loop for a given transaction.
 *
 * @param {string} transactionId - Active transaction ID
 * @param {string} apiPrefix - Endpoint prefix (e.g. '/transaction', '/ewallet/transactions', '/forex/transaction')
 * @param {boolean} enabled - Whether polling is active
 * @param {function} onAccepted - Optional callback when bill is accepted (returns state data)
 */
export function useBillAcceptance(transactionId, apiPrefix, enabled, onAccepted) {
  const [isAccepting, setIsAccepting] = useState(false);
  const [lastError, setLastError] = useState(null);
  const { subscribe, unsubscribe } = useWebSocket();

  // Listen for WebSocket rejection events
  useEffect(() => {
    const handleBillRejected = (event) => {
      if (event.payload) {
        setLastError(event.payload.reason || event.payload.error || "BILL_REJECTED");
      }
    };

    subscribe("BILL_REJECTED", handleBillRejected);
    return () => {
      unsubscribe("BILL_REJECTED", handleBillRejected);
    };
  }, [subscribe, unsubscribe]);

  useEffect(() => {
    if (!transactionId || !enabled) return undefined;
    let cancelled = false;

    const acceptLoop = async () => {
      setIsAccepting(true);
      while (!cancelled) {
        try {
          const resp = await fetch(`${API_BASE}${apiPrefix}/${transactionId}/accept-bill`, {
            method: "POST",
          });
          
          if (!resp.ok) {
            await new Promise((resolve) => setTimeout(resolve, 1000));
            continue;
          }
          
          const data = await resp.json();
          if (cancelled) break;

          if (onAccepted) {
            onAccepted(data);
          }

          if (data?.state === "WAITING_FOR_CONFIRMATION" || data?.state === "COMPLETE") {
            break;
          }

          if (data?.last_rejection || data?.error) {
            setLastError(data.last_rejection || data.error);
          }
        } catch (err) {
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      }
      setIsAccepting(false);
    };

    acceptLoop();

    return () => {
      cancelled = true;
    };
  }, [transactionId, apiPrefix, enabled, onAccepted]);

  const clearError = () => setLastError(null);

  return { isAccepting, lastError, clearError };
}
