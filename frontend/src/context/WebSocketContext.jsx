/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useCallback,
} from "react";
import { WS_URL } from "../constants/api";

const WebSocketContext = createContext(null);

const CONNECTION_STATES = {
  CONNECTING: "CONNECTING",
  OPEN: "OPEN",
  CLOSED: "CLOSED",
  RECONNECTING: "RECONNECTING",
};

const MAX_RECONNECT_DELAY = 30000; // 30 seconds
const HEARTBEAT_INTERVAL = 30000; // 30 seconds

export function WebSocketProvider({ children }) {
  const [connectionState, setConnectionState] = useState(
    CONNECTION_STATES.CONNECTING
  );
  const wsRef = useRef(null);
  const listenersRef = useRef(new Map());
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef(null);
  const heartbeatTimerRef = useRef(null);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionState(CONNECTION_STATES.OPEN);
        reconnectAttemptRef.current = 0;

        // Start heartbeat
        heartbeatTimerRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: "PING" }));
          }
        }, HEARTBEAT_INTERVAL);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const eventType = data.type;

          // Notify all listeners for this event type
          const callbacks = listenersRef.current.get(eventType);
          if (callbacks) {
            callbacks.forEach((cb) => {
              try {
                cb(data);
              } catch (err) {
                console.error("WebSocket listener error:", err);
              }
            });
          }

          // Also notify wildcard listeners
          const wildcardCallbacks = listenersRef.current.get("*");
          if (wildcardCallbacks) {
            wildcardCallbacks.forEach((cb) => {
              try {
                cb(data);
              } catch (err) {
                console.error("WebSocket wildcard listener error:", err);
              }
            });
          }
        } catch {
          // Ignore non-JSON messages
        }
      };

      ws.onclose = () => {
        clearInterval(heartbeatTimerRef.current);
        setConnectionState(CONNECTION_STATES.RECONNECTING);
        scheduleReconnect();
      };

      ws.onerror = () => {
        // onclose will fire after onerror
      };
    } catch {
      setConnectionState(CONNECTION_STATES.CLOSED);
      scheduleReconnect();
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    const attempt = reconnectAttemptRef.current;
    const delay = Math.min(1000 * Math.pow(2, attempt), MAX_RECONNECT_DELAY);
    reconnectAttemptRef.current += 1;

    reconnectTimerRef.current = setTimeout(() => {
      setConnectionState(CONNECTION_STATES.RECONNECTING);
      connect();
    }, delay);
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimerRef.current);
      clearInterval(heartbeatTimerRef.current);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const subscribe = useCallback((eventType, callback) => {
    if (!listenersRef.current.has(eventType)) {
      listenersRef.current.set(eventType, new Set());
    }
    listenersRef.current.get(eventType).add(callback);
  }, []);

  const unsubscribe = useCallback((eventType, callback) => {
    const callbacks = listenersRef.current.get(eventType);
    if (callbacks) {
      callbacks.delete(callback);
    }
  }, []);

  const sendMessage = useCallback((action, data = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, data }));
    }
  }, []);

  const value = {
    connectionState,
    isConnected: connectionState === CONNECTION_STATES.OPEN,
    subscribe,
    unsubscribe,
    sendMessage,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocket() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  }
  return context;
}

export default WebSocketContext;
