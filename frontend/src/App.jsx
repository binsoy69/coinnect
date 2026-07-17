import { useEffect, useState, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import AppRoutes from './routes';
import { useWebSocket } from './context/WebSocketContext';
import { ROUTES } from './constants/routes';
import { API_BASE } from './constants/api';
import StartupChecksScreen from './pages/StartupChecksScreen';

const TOKEN_KEY = "coinnect_admin_token";

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const { subscribe, unsubscribe, isConnected } = useWebSocket();
  const [startupState, setStartupState] = useState(null);
  const [isConnecting, setIsConnecting] = useState(true);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/status`);
      if (response.ok) {
        const data = await response.json();
        setStartupState(data.startup_checks);
        setIsConnecting(false);
      } else {
        setIsConnecting(true);
      }
    } catch (err) {
      console.error("Failed to fetch initial system status:", err);
      setIsConnecting(true);
    }
  }, []);

  useEffect(() => {
    if (isConnected) {
      fetchStatus();
    } else {
      setIsConnecting(true);
    }
  }, [isConnected, fetchStatus]);

  useEffect(() => {
    const handleStateChange = (event) => {
      if (
        event.payload &&
        event.payload.mode === 'maintenance' &&
        event.payload.admin_session
      ) {
        sessionStorage.setItem(TOKEN_KEY, event.payload.admin_session.token);
        navigate(ROUTES.ADMIN_INVENTORY, { replace: true });
      }

      if (event.payload && event.payload.startup_checks) {
        setStartupState(event.payload.startup_checks);
      }
    };

    subscribe('STATE_CHANGE', handleStateChange);
    return () => {
      unsubscribe('STATE_CHANGE', handleStateChange);
    };
  }, [subscribe, unsubscribe, navigate]);

  // Show startup checks if they are in progress or failed
  const showDiagnostics = isConnecting || !startupState || !startupState.performed || startupState.has_errors;

  if (showDiagnostics) {
    return (
      <StartupChecksScreen
        startupChecks={startupState}
        isConnecting={isConnecting}
      />
    );
  }

  return (
    <AnimatePresence mode="wait">
      <div key={location.pathname}>
        <AppRoutes />
      </div>
    </AnimatePresence>
  );
}

export default App;

