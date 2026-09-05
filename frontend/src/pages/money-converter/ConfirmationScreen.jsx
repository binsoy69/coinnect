import { useNavigate, useParams } from "react-router-dom";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import Button from "../../components/common/Button";
import PageTransition from "../../components/layout/PageTransition";
import { ROUTES, getServiceRoute } from "../../constants/routes";
import { useTransaction } from "../../context/TransactionContext";
import { useBackendTransaction } from "../../hooks/useBackendTransaction";
import { formatPeso } from "../../constants/denominations";

// Question mark icon
const QuestionIcon = () => (
  <div className="w-20 h-20 mx-auto mb-4 rounded-full border-4 border-white flex items-center justify-center">
    <span className="text-4xl font-bold text-white">?</span>
  </div>
);

export default function ConfirmationScreen() {
  const navigate = useNavigate();
  const { type } = useParams();
  const { transaction, currentQuote, setCurrentQuote } = useTransaction();
  const {
    startBackendTransaction,
    cancelBackendTransaction,
    createQuote,
    transactionId,
    backendState,
  } = useBackendTransaction();

  const [isStarting, setIsStarting] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [quoteChangedNotice, setQuoteChangedNotice] = useState(null);

  // Active quote: prioritize currentQuote from context, then backendState quote
  const activeQuote = currentQuote || backendState?.approved_quote || backendState?.pending_quote;

  // If no quote exists yet (e.g. direct link or page reload), fetch one
  useEffect(() => {
    let mounted = true;
    if (!activeQuote && transaction.selectedAmount && type) {
      createQuote(type, transaction.selectedAmount, null)
        .then((q) => {
          if (mounted && q) setCurrentQuote(q);
        })
        .catch((err) => {
          if (mounted) setErrorMsg(err.message || "Failed to load payout proposal.");
        });
    }
    return () => {
      mounted = false;
    };
  }, [activeQuote, transaction.selectedAmount, type, createQuote, setCurrentQuote]);

  const netPayoutAmount = activeQuote?.payout_amount ?? (
    type === "coin-to-bill"
      ? (transaction.selectedAmount || 0)
      : Math.max(0, (transaction.selectedAmount || 0) - (transaction.fee || 0))
  );

  const totalToInsert = activeQuote?.total_due ?? transaction.totalDue;
  const transactionFee = activeQuote?.fee ?? transaction.fee;

  // Payout items breakdown
  const items = activeQuote?.items || [];
  const bills = items.filter((i) => i.denom_type === "bill" || !i.denom_type);
  const coins = items.filter((i) => i.denom_type === "coin");
  const coinSum = coins.reduce((sum, c) => sum + Number(c.value) * (c.count || 0), 0);

  const handleBack = async () => {
    if (transactionId) {
      try {
        await cancelBackendTransaction();
      } catch {
        // Continue navigation if cancel fails
      }
    }
    navigate(getServiceRoute(ROUTES.SELECT_AMOUNT, type));
  };

  const handleProceed = async () => {
    setIsStarting(true);
    setErrorMsg(null);
    setQuoteChangedNotice(null);

    try {
      await startBackendTransaction(
        type,
        activeQuote?.input_amount || transaction.selectedAmount,
        transaction.selectedDispenseDenominations || [],
        transaction.selectedDispenseCounts || null,
        activeQuote?.id || null
      );
      navigate(getServiceRoute(ROUTES.INSERT_MONEY, type));
    } catch (err) {
      if (err.code === "QUOTE_CHANGED" && err.quote) {
        // Update to new proposal and prompt customer
        setCurrentQuote(err.quote);
        setQuoteChangedNotice(
          "Available inventory changed. A revised payout proposal has been updated below for your review."
        );
      } else {
        setErrorMsg(
          err.message ||
            "Failed to start transaction. Please check machine inventory and try again."
        );
      }
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <PageTransition>
      <div className="min-h-screen bg-coinnect-primary flex flex-col items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center text-white max-w-2xl w-full"
        >
          {/* Question icon */}
          <div className="transform scale-90">
            <QuestionIcon />
          </div>

          {/* Quote changed banner notice */}
          {quoteChangedNotice && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-amber-400 text-amber-950 font-bold p-4 rounded-2xl mb-4 text-sm shadow-lg border border-amber-300"
            >
              ⚠️ {quoteChangedNotice}
            </motion.div>
          )}

          {/* Substitution Notice */}
          {activeQuote?.is_substitution && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-amber-500/25 border-2 border-amber-300 text-amber-100 p-4 rounded-2xl mb-4 text-left shadow-lg backdrop-blur-md"
            >
              <div className="flex items-center gap-2 text-amber-200 font-bold text-sm mb-1 uppercase tracking-wide">
                <span className="text-xl">⚠️</span> Stock Substitution Notice
              </div>
              <p className="text-sm font-medium leading-relaxed">
                {activeQuote.substitution_notice ||
                  "Some requested denominations were substituted with available bills/coins to complete your exact payout amount."}
              </p>
            </motion.div>
          )}

          {/* Amount details */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mb-3"
          >
            <p className="text-xl">
              Amount Selected:{" "}
              <span className="font-bold">
                {formatPeso(activeQuote?.input_amount || transaction.selectedAmount || 0)}
              </span>
              {" | "}
              Transaction Fee:{" "}
              <span className="font-bold">{formatPeso(transactionFee)}</span>
            </p>
          </motion.div>

          {/* Total Due & Total to Dispense */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mb-6 space-y-1"
          >
            <p className="text-3xl font-bold">
              Total Cash to Insert: {formatPeso(totalToInsert)}
            </p>
            <p className="text-2xl font-extrabold text-amber-300">
              Total Cash to Dispense: {formatPeso(netPayoutAmount)}
            </p>
          </motion.div>

          {/* Dispense Breakdown Summary */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="bg-white/10 backdrop-blur-md rounded-2xl p-5 mb-6 border border-white/20 max-w-lg mx-auto shadow-lg"
          >
            <p className="text-sm font-semibold uppercase tracking-wider text-white/80 mb-3">
              Planned Dispense Breakdown
            </p>

            <div className="flex flex-wrap gap-3 justify-center mb-2">
              {/* Bills */}
              {bills.map((item, idx) => (
                <div
                  key={`b-${idx}-${item.value}`}
                  className="bg-white/20 border border-white/30 px-4 py-2 rounded-xl text-lg font-bold text-white shadow-sm flex items-center gap-1.5"
                >
                  <span className="text-xs bg-white/30 px-1.5 py-0.5 rounded font-mono">Bill</span>
                  {item.count}x {formatPeso(item.value)}
                </div>
              ))}

              {/* Coins */}
              {coins.map((item, idx) => (
                <div
                  key={`c-${idx}-${item.value}`}
                  className="bg-amber-400/30 border border-amber-300/40 px-4 py-2 rounded-xl text-lg font-bold text-amber-200 shadow-sm flex items-center gap-1.5"
                >
                  <span className="text-xs bg-amber-400/40 text-amber-100 px-1.5 py-0.5 rounded font-mono">Coin</span>
                  {item.count}x {formatPeso(item.value)}
                </div>
              ))}
            </div>

            {coinSum > 0 && type !== "bill-to-coin" && (
              <p className="text-xs text-amber-200 bg-amber-500/20 border border-amber-400/30 rounded-xl py-2 px-3 mt-3 font-semibold">
                ⚠️ Note: {formatPeso(coinSum)} remainder will be dispensed in coins.
              </p>
            )}
          </motion.div>

          {/* Instruction */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-lg mb-8 text-white/90"
          >
            Click Proceed to Continue.
          </motion.p>

          {/* Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="flex gap-6 justify-center"
          >
            <Button
              variant="outline"
              size="xl"
              onClick={handleBack}
              className="px-12"
            >
              Back
            </Button>
            <Button
              variant="white"
              size="xl"
              onClick={handleProceed}
              className="px-12"
              disabled={isStarting || !activeQuote}
            >
              {isStarting ? "Starting..." : "Proceed"}
            </Button>
          </motion.div>
        </motion.div>
      </div>

      {errorMsg && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center p-4 z-50">
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            className="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl text-center border border-gray-100"
          >
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-8 h-8 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            
            <h3 className="text-2xl font-bold text-gray-900 mb-3">
              Transaction Error
            </h3>
            
            <p className="text-gray-600 mb-8 leading-relaxed">
              {errorMsg}
            </p>
            
            <div className="flex gap-4">
              <Button
                variant="outline"
                size="lg"
                onClick={() => setErrorMsg(null)}
                className="flex-1 text-gray-700 border-gray-300"
              >
                Close
              </Button>
              <Button
                variant="primary"
                size="lg"
                onClick={() => navigate(ROUTES.HOME)}
                className="flex-1 bg-coinnect-primary text-white"
              >
                Home
              </Button>
            </div>
          </motion.div>
        </div>
      )}
    </PageTransition>
  );
}
