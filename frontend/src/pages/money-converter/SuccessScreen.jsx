import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import Button from "../../components/common/Button";
import SuccessIcon from "../../components/feedback/SuccessIcon";
import PageTransition from "../../components/layout/PageTransition";
import { ROUTES } from "../../constants/routes";
import { useTransaction } from "../../context/TransactionContext";

export default function SuccessScreen() {
  const navigate = useNavigate();
  const { resetTransaction } = useTransaction();

  const handleExit = () => {
    resetTransaction();
    navigate(ROUTES.HOME);
  };

  const handleAnotherTransaction = () => {
    resetTransaction();
    navigate(ROUTES.SELECT_TRANSACTION);
  };

  return (
    <PageTransition>
      <div className="min-h-screen bg-coinnect-primary flex flex-col items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center text-white max-w-2xl"
        >
          {/* Success icon */}
          <div className="flex justify-center mb-6">
            <SuccessIcon size={120} />
          </div>

          {/* Success message */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="text-3xl font-bold mb-2"
          >
            Successfully dispensed the money!
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="text-lg text-white/90 mb-8"
          >
            Check the money dispenser and receipt.
          </motion.p>

          {/* Action buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="flex gap-4 justify-center"
          >
            <Button
              variant="outline"
              size="xl"
              onClick={handleExit}
              className="px-8"
            >
              Exit
            </Button>
            <Button
              variant="white"
              size="xl"
              onClick={handleAnotherTransaction}
              className="px-8"
            >
              Another Transaction
            </Button>
          </motion.div>
        </motion.div>
      </div>
    </PageTransition>
  );
}
