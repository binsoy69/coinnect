import { useEffect, useState, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import AppRoutes from './routes';
import { useWebSocket } from './context/WebSocketContext';
import { useForex } from './context/ForexContext';
import { useTransaction } from './context/TransactionContext';
import { ROUTES, getServiceRoute, getForexRoute } from './constants/routes';
import { API_BASE } from './constants/api';
import StartupChecksScreen from './pages/StartupChecksScreen';

const TOKEN_KEY = "coinnect_admin_token";

function App() {
  const location = useLocation();
  const { backendState } = useTransaction();
  const { backendState: forexState, forex } = useForex();
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
    if (!forexState || !forex.serviceType || !(location.pathname.startsWith('/forex') || location.pathname === '/')) return;
    let route;
    if (forexState.state === 'COMPLETE') route = ROUTES.FOREX_SUCCESS;
    else if (['CLAIM_REQUIRED', 'ERROR', 'CANCELLED', 'RESOLVED'].includes(forexState.state)) route = ROUTES.FOREX_WARNING;
    else if (forexState.state === 'DISPENSING') route = ROUTES.FOREX_PROCESSING;
    else if (location.pathname === '/' || ['/forex', '/forex/reminder'].includes(location.pathname) || location.pathname.endsWith('/rate') || location.pathname.endsWith('/confirm')) {
      route = forexState.state === 'WAITING_FOR_CONFIRMATION' ? ROUTES.FOREX_SUMMARY : ROUTES.FOREX_INSERT;
    }
    if (route) {
      const destination = getForexRoute(route, forex.serviceType);
      if (location.pathname !== destination) navigate(destination, { replace: true });
    }
  }, [forexState, forex.serviceType, location.pathname, navigate]);

  useEffect(() => {
    const task = setTimeout(() => {
      if (isConnected) fetchStatus();
      else setIsConnecting(true);
    }, 0);
    return () => clearTimeout(task);
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

  useEffect(() => {
    if (!backendState?.type || !(location.pathname.startsWith('/money-converter') || location.pathname === '/')) return;
    const state = backendState.state;
    let route = null;
    if (state === 'COMPLETE') route = ROUTES.SUCCESS;
    else if (['CLAIM_REQUIRED', 'ERROR', 'CANCELLED'].includes(state)) route = ROUTES.WARNING;
    else if (state === 'DISPENSING' || backendState.pending_quote) route = ROUTES.PROCESSING;
    else if (location.pathname === '/') route = state === 'WAITING_FOR_CONFIRMATION' ? ROUTES.TRANSACTION_SUMMARY : ROUTES.INSERT_MONEY;
    if (route) {
      const destination = getServiceRoute(route, backendState.type);
      if (location.pathname !== destination) navigate(destination, { replace: true });
    }
  }, [backendState, location.pathname, navigate]);

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

