import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { TransactionProvider } from './context/TransactionContext';
import { ForexProvider } from './context/ForexContext';
import './index.css';
import App from './App.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <TransactionProvider>
        <ForexProvider>
          <App />
        </ForexProvider>
      </TransactionProvider>
    </BrowserRouter>
  </StrictMode>,
);
