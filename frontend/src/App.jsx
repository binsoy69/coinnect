import { useLocation } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import AppRoutes from './routes';

function App() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <div key={location.pathname}>
        <AppRoutes />
      </div>
    </AnimatePresence>
  );
}

export default App;
