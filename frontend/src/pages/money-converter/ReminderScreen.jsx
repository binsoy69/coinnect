import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import Button from "../../components/common/Button";
import PageTransition from "../../components/layout/PageTransition";
import { ROUTES, getServiceRoute } from "../../constants/routes";
import { useTransaction } from "../../context/TransactionContext";

// Kiosk with smiley face SVG
const KioskIcon = () => (
  <svg
    viewBox="0 0 200 200"
    className="w-48 h-48 mx-auto mb-8"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    {/* Kiosk body */}
    <rect
      x="50"
      y="30"
      width="100"
      height="140"
      rx="10"
      fill="white"
      fillOpacity="0.95"
    />
    {/* Screen */}
    <rect x="60" y="40" width="80" height="70" rx="5" fill="#1E3A5F" />
    {/* Smiley face on screen */}
    <circle cx="85" cy="70" r="5" fill="white" /> {/* Left eye */}
    <circle cx="115" cy="70" r="5" fill="white" /> {/* Right eye */}
    <path
      d="M80 85 Q100 100 120 85"
      stroke="white"
      strokeWidth="3"
      strokeLinecap="round"
      fill="none"
    />{" "}
    {/* Smile */}
    {/* Keypad area */}
    <rect x="65" y="120" width="70" height="40" rx="3" fill="#E5E7EB" />
    {/* Keypad buttons */}
    {[0, 1, 2].map((row) =>
      [0, 1, 2].map((col) => (
        <rect
          key={`${row}-${col}`}
          x={72 + col * 20}
          y={125 + row * 12}
          width="14"
          height="8"
          rx="2"
          fill="#9CA3AF"
        />
      )),
    )}
    {/* Card slot */}
    <rect x="130" y="80" width="15" height="4" rx="2" fill="#6B7280" />
    {/* Receipt slot */}
    <rect x="75" y="165" width="50" height="3" rx="1" fill="#6B7280" />
  </svg>
);

export default function ReminderScreen() {
  const navigate = useNavigate();
  const { transaction } = useTransaction();

  const handleProceed = () => {
    if (transaction.serviceType) {
      navigate(getServiceRoute(ROUTES.SELECT_AMOUNT, transaction.serviceType));
    }
  };

  return (
    <PageTransition>
      <div className="min-h-screen bg-coinnect-primary flex flex-col items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center text-white max-w-2xl"
        >
          {/* Kiosk illustration */}
          <div className="transform scale-75 origin-bottom">
            <KioskIcon />
          </div>

          {/* Reminder heading */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-3xl font-bold mb-4"
          >
            REMINDER:
          </motion.h1>

          {/* Disclaimer text */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-lg leading-relaxed mb-8 text-white/90"
          >
            Once you insert money, it cannot be refunded unless affected by
            uncontrollable circumstances.{" "}
            <span className="font-bold">
              PLEASE REVIEW YOUR TRANSACTION CAREFULLY.
            </span>
          </motion.p>

          {/* Proceed button */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <Button
              variant="outline"
              size="xl"
              onClick={handleProceed}
              className="px-16"
            >
              Proceed
            </Button>
          </motion.div>
        </motion.div>
      </div>
    </PageTransition>
  );
}
