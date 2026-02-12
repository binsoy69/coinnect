import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { WebSocketProvider } from './context/WebSocketContext';
import { TransactionProvider } from './context/TransactionContext';
import { ForexProvider } from './context/ForexContext';
import { EWalletProvider } from './context/EWalletContext';
import './index.css';
import App from './App.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <WebSocketProvider>
        <TransactionProvider>
          <ForexProvider>
            <EWalletProvider>
              <App />
            </EWalletProvider>
          </ForexProvider>
        </TransactionProvider>
      </WebSocketProvider>
    </BrowserRouter>
  </StrictMode>,
);
