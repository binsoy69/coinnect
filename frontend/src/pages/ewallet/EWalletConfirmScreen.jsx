import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { HelpCircle } from "lucide-react";
import Button from "../../components/common/Button";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";
import { isCashIn } from "../../constants/ewalletData";

export default function EWalletConfirmScreen() {
  const navigate = useNavigate();
  const {
    ewallet,
    getEWalletConfig,
    getProviderStyles,
    startBackendTransaction,
    acceptPolicy,
    obtainQuote,
  } = useEWallet();
  const config = getEWalletConfig();
  const styles = getProviderStyles();
  const [submitting, setSubmitting] = useState(false);
  const [quoteMessage, setQuoteMessage] = useState("");

  if (!config) {
    navigate(ROUTES.EWALLET);
    return null;
  }

  const handleProceed = async () => {
    if (submitting || (isCashIn(ewallet.serviceType) && !ewallet.policyAccepted)) return;
    setSubmitting(true);
    try {
      await startBackendTransaction();
    // Branching: Cash In goes to insert bills, Cash Out goes to QR code
      if (isCashIn(ewallet.serviceType)) {
        navigate(
          getEWalletRoute(ROUTES.EWALLET_INSERT_BILLS, ewallet.serviceType),
        );
      } else {
        navigate(getEWalletRoute(ROUTES.EWALLET_QR, ewallet.serviceType));
      }
    } catch (error) {
      if (["QUOTE_CHANGED", "QUOTE_EXPIRED"].includes(error.code)) {
        try {
          await obtainQuote(ewallet.totalDue);
          setQuoteMessage("The quote was updated. Review the amount, fee, and intake options, then confirm again.");
        } catch (quoteError) { setQuoteMessage(quoteError.message); }
      }
    } finally {
      setSubmitting(false);
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

      {isCashIn(ewallet.serviceType) && <div className="max-w-2xl rounded-xl bg-white p-5 text-gray-900 mb-6 space-y-3">
        <p>Change is available in coins only, up to ₱20, subject to available stock. Bills requiring more change will be returned.</p>
        <p>After cash is accepted, you cannot cancel. If you leave a partially paid transaction inactive for 120 seconds, the kiosk will retain the inserted cash without wallet credit or a claim ticket. Tap Continue to keep your session active.</p>
        <label className="flex gap-3 items-start font-semibold"><input type="checkbox" checked={ewallet.policyAccepted}
          onChange={event => acceptPolicy(event.target.checked)} className="mt-1 h-6 w-6" />I understand and accept these cash-in rules.</label>
      </div>}

      {/* Confirmation Details */}
      {quoteMessage && <p role="alert" className="max-w-2xl rounded-xl bg-white p-4 mb-4">{quoteMessage}</p>}
      <motion.div
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="text-center text-white mb-8"
      >
        {isCashIn(ewallet.serviceType) && (
          <>
            <p className="text-xl mb-4">
              <span className="font-normal">Account Name: </span>
              <span className="font-bold">{ewallet.accountName}</span>
            </p>
            <p className="text-xl mb-4">
              <span className="font-normal">Mobile Number: </span>
              <span className="font-bold">{ewallet.mobileNumber}</span>
            </p>
          </>
        )}
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
          disabled={submitting}
          className="min-w-[150px] border-white text-white hover:bg-white/10"
        >
          Back
        </Button>
        <Button
          variant={ewallet.provider === "maya" ? "white-green" : "white-blue"}
          size="xl"
          onClick={handleProceed}
          disabled={submitting || (isCashIn(ewallet.serviceType) && !ewallet.policyAccepted)}
          className="min-w-[150px]"
        >
          {submitting ? "Connecting..." : "Proceed"}
        </Button>
        {ewallet.gatewayError && (
          <p className="text-white bg-red-700/50 rounded-lg px-4 py-2">
            {ewallet.gatewayError}
          </p>
        )}
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
