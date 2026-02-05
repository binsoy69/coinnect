import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import SuccessIcon from "../../components/feedback/SuccessIcon";
import Button from "../../components/common/Button";
import { ROUTES } from "../../constants/routes";
import { useForex } from "../../context/ForexContext";

export default function ForexSuccessScreen() {
  const navigate = useNavigate();
  const { resetForexTransaction } = useForex();

  const handleExit = () => {
    resetForexTransaction();
    navigate(ROUTES.HOME);
  };

  const handleAnotherTransaction = () => {
    resetForexTransaction();
    navigate(ROUTES.SELECT_TRANSACTION);
  };

  return (
    <div className="min-h-screen bg-coinnect-forex flex flex-col items-center justify-center p-8">
      {/* Success Icon */}
      <motion.div
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ type: "spring", duration: 0.5 }}
        className="mb-8"
      >
        <SuccessIcon size={150} />
      </motion.div>

      {/* Success Message */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="text-center text-white mb-10"
      >
        <h1 className="text-3xl font-bold mb-2">
          Successfully dispensed excess money!
        </h1>
        <p className="text-xl">Check the cash tray.</p>
      </motion.div>

      {/* Buttons */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="flex gap-4 w-full max-w-2xl justify-center"
      >
        <Button
          variant="outline"
          size="xl"
          onClick={handleExit}
          className="bg-transparent border-white text-white hover:bg-white/10 w-full"
        >
          Exit
        </Button>
        <Button
          variant="white"
          size="xl"
          onClick={handleAnotherTransaction}
          className="w-full !text-coinnect-forex"
        >
          Another Transaction
        </Button>
      </motion.div>
    </div>
  );
}
