import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { HelpCircle } from "lucide-react";
import Button from "../../components/common/Button";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";
import { isCashIn } from "../../constants/ewalletData";

export default function EWalletConfirmScreen() {
  const navigate = useNavigate();
  const { ewallet, getEWalletConfig, getProviderStyles } = useEWallet();
  const config = getEWalletConfig();
  const styles = getProviderStyles();

  if (!config) {
    navigate(ROUTES.EWALLET);
    return null;
  }

  const handleProceed = () => {
    // Branching: Cash In goes to insert bills, Cash Out goes to QR code
    if (isCashIn(ewallet.serviceType)) {
      navigate(
        getEWalletRoute(ROUTES.EWALLET_INSERT_BILLS, ewallet.serviceType),
      );
    } else {
      navigate(getEWalletRoute(ROUTES.EWALLET_QR, ewallet.serviceType));
    }
  };

  const handleBack = () => {
    navigate(getEWalletRoute(ROUTES.EWALLET_AMOUNT, ewallet.serviceType));
  };

  return (
    <div
      className={`min-h-screen ${styles.bg} flex flex-col items-center justify-center p-8`}
    >
      {/* Question Mark Icon */}
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.3 }}
        className="mb-8"
      >
        <div className="w-32 h-32 rounded-full border-4 border-white flex items-center justify-center">
          <HelpCircle className="w-20 h-20 text-white" strokeWidth={1.5} />
        </div>
      </motion.div>

      {/* Confirmation Details */}
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="text-center text-white mb-8"
      >
        <p className="text-xl mb-4">
          <span className="font-normal">Mobile Number: </span>
          <span className="font-bold">
            {ewallet.mobileNumber || "09XXXXXXXXX"}
          </span>
        </p>
        <p className="text-xl mb-4">
          <span className="font-normal">Amount to Transfer: </span>
          <span className="font-bold">P{ewallet.transferAmount}</span>
          <span className="mx-2">|</span>
          <span className="font-normal">Transaction Fee: </span>
          <span className="font-bold">P{ewallet.fee}</span>
        </p>
        <p className="text-xl mb-4">
          <span className="font-normal">Total Due: </span>
          <span className="font-bold">P{ewallet.totalDue}</span>
        </p>
        <p className="text-xl font-semibold mt-6">
          Click <span className="font-bold">Proceed</span> to Continue.
        </p>
      </motion.div>

      {/* Buttons */}
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.4 }}
        className="flex gap-4"
      >
        <Button
          variant="outline"
          size="xl"
          onClick={handleBack}
          className="min-w-[150px] border-white text-white hover:bg-white/10"
        >
          Back
        </Button>
        <Button
          variant={ewallet.provider === "maya" ? "white-green" : "white-blue"}
          size="xl"
          onClick={handleProceed}
          className="min-w-[150px]"
        >
          Proceed
        </Button>
      </motion.div>

      {/* Note */}
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="text-white/80 text-sm mt-8"
      >
        <span className="font-bold">Note:</span> The transaction fee is
        automatically deducted from the inserted amount.
      </motion.p>
    </div>
  );
}
