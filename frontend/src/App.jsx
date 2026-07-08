import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import AppRoutes from './routes';
import { useWebSocket } from './context/WebSocketContext';
import { ROUTES } from './constants/routes';

const TOKEN_KEY = "coinnect_admin_token";

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const { subscribe, unsubscribe } = useWebSocket();

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
    };

    subscribe('STATE_CHANGE', handleStateChange);
    return () => {
      unsubscribe('STATE_CHANGE', handleStateChange);
    };
  }, [subscribe, unsubscribe, navigate]);

  return (
    <AnimatePresence mode="wait">
      <div key={location.pathname}>
        <AppRoutes />
      </div>
    </AnimatePresence>
  );
}

export default App;
