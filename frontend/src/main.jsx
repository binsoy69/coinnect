import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { WebSocketProvider } from './context/WebSocketContext';
import { TransactionProvider } from './context/TransactionContext';
import { ForexProvider } from './context/ForexContext';
import { EWalletProvider } from './context/EWalletContext';
import ErrorBoundary from './components/common/ErrorBoundary';
import './index.css';
import App from './App.jsx';
import EWalletRouteGuard from './components/ewallet/EWalletRouteGuard';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <WebSocketProvider>
        <TransactionProvider>
          <ForexProvider>
            <EWalletProvider>
              <ErrorBoundary>
                <EWalletRouteGuard />
                <App />
              </ErrorBoundary>
            </EWalletProvider>
          </ForexProvider>
        </TransactionProvider>
      </WebSocketProvider>
    </BrowserRouter>
  </StrictMode>,
);
