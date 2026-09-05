import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import Button from "../common/Button";

export default function InactivityWarningModal({
  warningAt,
  expiresAt,
  serverTime,
  onKeepAlive,
  active = false,
}) {
  const [secondsRemaining, setSecondsRemaining] = useState(30);
  const [isWarningVisible, setIsWarningVisible] = useState(false);
  useEffect(() => {
    const receivedAt = Date.now();
    const serverAt = serverTime ? Date.parse(serverTime) : receivedAt;
    const check = () => {
      const now = serverAt + Date.now() - receivedAt;
      setIsWarningVisible(Boolean(active || (warningAt && now >= Date.parse(warningAt))));
      setSecondsRemaining(expiresAt ? Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / 1000)) : 30);
    };
    const interval = setInterval(check, 250);
    return () => clearInterval(interval);
  }, [warningAt, expiresAt, serverTime, active]);

  if (!isWarningVisible) return null;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 z-50">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 15 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl text-center border-2 border-amber-400"
      >
        <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4 text-amber-600 text-3xl font-extrabold animate-pulse">
          ⏱
        </div>

        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          Are you still there?
        </h2>

        <p className="text-gray-600 text-sm mb-4">
          Your transaction has been inactive and will expire in:
        </p>

        <div className="text-5xl font-black text-amber-600 mb-4 font-mono tracking-tight">
          {secondsRemaining}s
        </div>

        <p className="text-xs text-gray-500 mb-6 leading-relaxed">
          If the session expires, any cash already inserted will be preserved and refunded with a claim ticket.
        </p>

        <Button
          variant="primary"
          size="xl"
          onClick={() => {
            setIsWarningVisible(false);
            onKeepAlive?.();
          }}
          className="w-full py-5 text-lg font-bold shadow-lg"
        >
          I'm Still Here (Continue)
        </Button>
      </motion.div>
    </div>
  );
}
