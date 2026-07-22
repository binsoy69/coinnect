import { useNavigate, useParams } from "react-router-dom";
import { useState } from "react";
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

function calculateAutoBreakdown(amount, preferredBillDenoms = []) {
  if (!amount || amount <= 0) return { bills: {}, coins: {}, coinSum: 0 };

  // Available bill denoms to try: use preferred if provided, otherwise standard [500, 100, 50, 20]
  // Strictly respects user preferred bill choices without introducing unselected bills (e.g. 200)
  const availableBillDenoms = preferredBillDenoms.length > 0
    ? [...preferredBillDenoms].sort((a, b) => b - a)
    : [500, 100, 50, 20];

  const coinDenoms = [20, 10, 5, 1];
  let rem = amount;
  const bills = {};
  const coins = {};

  // Phase 1: Bills
  for (const d of availableBillDenoms) {
    if (rem >= d) {
      const count = Math.floor(rem / d);
      bills[d] = count;
      rem %= d;
    }
  }

  // Phase 2: Coins for remainder (e.g., 15, 35, 5)
  if (rem > 0) {
    for (const c of coinDenoms) {
      if (rem >= c) {
        const count = Math.floor(rem / c);
        coins[c] = count;
        rem %= c;
      }
    }
  }

  const coinSum = Object.entries(coins).reduce((sum, [d, c]) => sum + Number(d) * c, 0);

  return { bills, coins, coinSum };
}

export default function ConfirmationScreen() {
  const navigate = useNavigate();
  const { type } = useParams();
  const { transaction } = useTransaction();
  const { startBackendTransaction, cancelBackendTransaction, transactionId } = useBackendTransaction();
  const [isStarting, setIsStarting] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);

  // Net amount to dispense: if fee not included, deduct fee from payout
  const netPayoutAmount = transaction.includeFee
    ? (transaction.selectedAmount || 0)
    : Math.max(0, (transaction.selectedAmount || 0) - (transaction.fee || 0));

  const userCounts = transaction.selectedDispenseCounts || {};
  const userAllocatedSum = Object.entries(userCounts).reduce(
    (sum, [d, c]) => sum + Number(d) * (c || 0),
    0
  );

  const breakdownObj = userAllocatedSum === netPayoutAmount && userAllocatedSum > 0
    ? { bills: userCounts, coins: {}, coinSum: 0 }
    : calculateAutoBreakdown(netPayoutAmount, transaction.selectedDispenseDenominations || []);

  // Merge bills and coins dictionary for backend transaction start
  const effectiveDispenseCounts = {
    ...breakdownObj.bills,
    ...breakdownObj.coins,
  };

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
    try {
      // Start backend transaction before navigating to insert screen
      await startBackendTransaction(
        type,
        transaction.selectedAmount,
        transaction.fee,
        transaction.selectedDispenseDenominations,
        effectiveDispenseCounts
      );
      navigate(getServiceRoute(ROUTES.INSERT_MONEY, type));
    } catch (err) {
      setErrorMsg(err.message || "Failed to start transaction. Please check machine inventory and try again.");
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
                {formatPeso(transaction.selectedAmount || 0)}
              </span>
              {" | "}
              Transaction Fee:{" "}
              <span className="font-bold">{formatPeso(transaction.fee)}</span>
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
              Total Cash to Insert: {formatPeso(transaction.totalDue)}
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
              {Object.entries(breakdownObj.bills).map(([denom, count]) => (
                <div
                  key={`bill-${denom}`}
                  className="bg-white/20 border border-white/30 px-4 py-2 rounded-xl text-lg font-bold text-white shadow-sm flex items-center gap-1.5"
                >
                  <span className="text-xs bg-white/30 px-1.5 py-0.5 rounded font-mono">Bill</span>
                  {count}x {formatPeso(denom)}
                </div>
              ))}

              {/* Coins */}
              {Object.entries(breakdownObj.coins).map(([denom, count]) => (
                <div
                  key={`coin-${denom}`}
                  className="bg-amber-400/30 border border-amber-300/40 px-4 py-2 rounded-xl text-lg font-bold text-amber-200 shadow-sm flex items-center gap-1.5"
                >
                  <span className="text-xs bg-amber-400/40 text-amber-100 px-1.5 py-0.5 rounded font-mono">Coin</span>
                  {count}x {formatPeso(denom)}
                </div>
              ))}
            </div>

            {breakdownObj.coinSum > 0 && (
              <p className="text-xs text-amber-200 bg-amber-500/20 border border-amber-400/30 rounded-xl py-2 px-3 mt-3 font-semibold">
                ⚠️ Note: {formatPeso(breakdownObj.coinSum)} remainder will be dispensed in coins.
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
              disabled={isStarting}
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
