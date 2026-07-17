import { useState } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, AlertCircle, Loader2, RefreshCw, Wrench } from 'lucide-react';
import { API_BASE } from '../constants/api';
import Button from '../components/common/Button';

export default function StartupChecksScreen({ startupChecks, isConnecting }) {
  const [retrying, setRetrying] = useState(false);

  const handleRetry = async () => {
    if (retrying) return;
    setRetrying(true);
    try {
      const response = await fetch(`${API_BASE}/status/startup-checks/retry`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error('Failed to trigger diagnostic retry');
      }
    } catch (err) {
      console.error('Error retrying checks:', err);
    } finally {
      // Keep loading spinner active briefly for better UX
      setTimeout(() => setRetrying(false), 2000);
    }
  };

  const checkItems = [
    {
      key: 'arduino_bill',
      name: 'Arduino Mega #1 (Bill Controller)',
      description: 'Manages bill sorting linear rail, dispensers, and optical sensors.',
    },
    {
      key: 'arduino_coin',
      name: 'Arduino Mega #2 (Coin & Security)',
      description: 'Manages coin acceptance, coin dispensers, shock sensors, and door solenoid lock.',
    },
    {
      key: 'camera',
      name: 'USB Camera',
      description: 'Captures ultraviolet and visible light images of inserted banknotes.',
    },
    {
      key: 'printer',
      name: 'Paperang P1 Printer',
      description: 'Prints receipts and customer shortfall claim tickets via Bluetooth.',
    },
    {
      key: 'yolo_models',
      name: 'YOLO ML Models',
      description: 'Banknote authentication and denomination identification models.',
    },
  ];

  const getStatus = (itemKey) => {
    if (isConnecting) return 'checking';
    if (!startupChecks || !startupChecks.performed) return 'checking';
    
    const errors = startupChecks.errors || {};
    if (itemKey in errors) {
      return 'error';
    }
    return 'ok';
  };

  const getErrorDetail = (itemKey) => {
    if (!startupChecks) return null;
    return startupChecks.errors ? startupChecks.errors[itemKey] : null;
  };

  return (
    <div className="min-h-screen bg-navy-gradient flex flex-col justify-between p-8 text-white select-none">
      {/* Top Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-6">
        <div className="flex items-center space-x-4">
          <Wrench className="h-10 w-10 text-coinnect-primary animate-pulse" />
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight">Kiosk Diagnostic Mode</h1>
            <p className="text-sm text-white/60 font-light mt-0.5">Coinnect Kiosk Self-Service Controller</p>
          </div>
        </div>
        <div className="flex items-center space-x-2 bg-white/5 px-4 py-2 rounded-full border border-white/10">
          <div className={`h-2.5 w-2.5 rounded-full ${isConnecting ? 'bg-yellow-400 animate-ping' : 'bg-green-500'}`} />
          <span className="text-xs font-mono uppercase tracking-wider text-white/80">
            {isConnecting ? 'Connecting Backend...' : 'Backend Connected'}
          </span>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="my-auto max-w-4xl mx-auto w-full grid grid-cols-1 md:grid-cols-3 gap-8 py-8">
        
        {/* Left Side: Summary Panel */}
        <div className="md:col-span-1 bg-white/5 backdrop-blur-md rounded-card border border-white/10 p-6 flex flex-col justify-between">
          <div>
            <span className="text-xs font-mono uppercase tracking-widest text-coinnect-primary">SYSTEM STATUS</span>
            <h2 className="text-2xl font-bold mt-2 mb-4">Diagnostic Verification</h2>
            <p className="text-white/70 text-sm leading-relaxed font-light mb-6">
              Coinnect automatically verifies all connected hardware, microcontrollers, and neural network models prior to starting.
            </p>
            {startupChecks?.has_errors || isConnecting ? (
              <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-sm text-red-200">
                <p className="font-semibold flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
                  Action Required
                </p>
                <p className="text-xs text-red-200/80 mt-1 leading-relaxed">
                  One or more hardware modules are offline or failed to initialize. Please check cables, power lines, and model configuration.
                </p>
              </div>
            ) : (
              <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-4 text-sm text-green-200">
                <p className="font-semibold flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-400 flex-shrink-0" />
                  All Systems Nominal
                </p>
                <p className="text-xs text-green-200/80 mt-1 leading-relaxed">
                  All hardware and software systems verified. Starting Kiosk interface...
                </p>
              </div>
            )}
          </div>

          <div className="mt-8">
            <Button
              variant="primary"
              fullWidth
              size="lg"
              onClick={handleRetry}
              disabled={retrying || isConnecting}
              className="relative shadow-lg overflow-hidden group"
            >
              {retrying ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin mr-2" />
                  Running Checks...
                </>
              ) : (
                <>
                  <RefreshCw className="h-5 w-5 mr-2 group-hover:rotate-180 transition-transform duration-500" />
                  Retry Diagnostics
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Right Side: Check Items Checklist */}
        <div className="md:col-span-2 space-y-4">
          {checkItems.map((item, idx) => {
            const status = getStatus(item.key);
            const errDetail = getErrorDetail(item.key);

            return (
              <motion.div
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1 }}
                key={item.key}
                className="bg-white/5 backdrop-blur-md rounded-card border border-white/10 p-5 flex items-start justify-between hover:bg-white/[0.08] transition-colors"
              >
                <div className="flex-1 pr-4">
                  <h3 className="font-bold text-lg flex items-center gap-2">
                    {item.name}
                  </h3>
                  <p className="text-white/60 text-xs mt-1 leading-relaxed font-light">{item.description}</p>
                  
                  {errDetail && (
                    <motion.div 
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      className="mt-3 bg-red-950/40 border border-red-500/20 rounded-lg p-2 text-xs font-mono text-red-300 leading-normal"
                    >
                      {errDetail}
                    </motion.div>
                  )}
                </div>

                <div className="flex-shrink-0 pt-1">
                  {status === 'checking' && (
                    <Loader2 className="h-6 w-6 text-yellow-400 animate-spin" />
                  )}
                  {status === 'ok' && (
                    <CheckCircle2 className="h-6 w-6 text-green-500" />
                  )}
                  {status === 'error' && (
                    <AlertCircle className="h-6 w-6 text-red-500" />
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* Footer / Copyright */}
      <div className="text-center text-xs text-white/30 font-light border-t border-white/5 pt-4">
        Coinnect Financial Kiosk System &copy; {new Date().getFullYear()} &bull; Google Deepmind Pair Programming
      </div>
    </div>
  );
}
