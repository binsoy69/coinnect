import { useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import InsertMoneyPanel from "../../components/transaction/InsertMoneyPanel";
import Timer from "../../components/common/Timer";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";
import {
  EWALLET_BILL_DENOMINATIONS,
  EWALLET_ALL_DENOMINATIONS,
  EWALLET_TIMER_DURATIONS,
} from "../../constants/ewalletData";

export default function EWalletInsertBillsScreen() {
  const navigate = useNavigate();
  const {
    ewallet,
    addInsertedBill,
    getEWalletConfig,
    getProviderStyles,
    isAmountMatched,
  } = useEWallet();
  const config = getEWalletConfig();
  const styles = getProviderStyles();

  // Handle timeout - go to insert coins if partial, else to details
  const handleTimeout = useCallback(() => {
    if (isAmountMatched()) {
      navigate(getEWalletRoute(ROUTES.EWALLET_DETAILS, ewallet.serviceType));
    } else {
      // If not matched, go to coins screen to complete the amount
      navigate(
        getEWalletRoute(ROUTES.EWALLET_INSERT_COINS, ewallet.serviceType),
      );
    }
  }, [navigate, ewallet.serviceType, isAmountMatched]);

  // Keyboard simulation for testing (keys 1-6 = bill denominations)
  useEffect(() => {
    const handleKeyPress = (e) => {
      const keyMap = {
        1: EWALLET_BILL_DENOMINATIONS[0], // P20
        2: EWALLET_BILL_DENOMINATIONS[1], // P50
        3: EWALLET_BILL_DENOMINATIONS[2], // P100
        4: EWALLET_BILL_DENOMINATIONS[3], // P200
        5: EWALLET_BILL_DENOMINATIONS[4], // P500
        6: EWALLET_BILL_DENOMINATIONS[5], // P1000
      };

      if (keyMap[e.key]) {
        addInsertedBill(keyMap[e.key]);
      }
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [addInsertedBill]);

  // Auto-advance when amount is matched
  useEffect(() => {
    if (isAmountMatched()) {
      const timer = setTimeout(() => {
        navigate(getEWalletRoute(ROUTES.EWALLET_DETAILS, ewallet.serviceType));
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [ewallet.totalInserted, isAmountMatched, navigate, ewallet.serviceType]);

  if (!config) {
    navigate(ROUTES.EWALLET);
    return null;
  }

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: () =>
          navigate(
            getEWalletRoute(ROUTES.EWALLET_CONFIRM, ewallet.serviceType),
          ),
        subtitle: "Insert Bills",
        rightContent: (
          <div
            className={`flex items-center gap-2 ${styles.bg} text-white px-3 py-1 rounded-full text-sm`}
          >
            <img src={config.icon} alt={config.name} className="w-5 h-5" />
            E-Wallet / {config.displayName}
          </div>
        ),
      }}
    >
      <div className="flex gap-6 p-6 min-h-[calc(100vh-140px)]">
        {/* Left Panel - Instructions */}
        <div className="w-1/3">
          <InsertMoneyPanel
            variant="bill"
            cardVariant={ewallet.provider} // 'gcash' or 'maya'
            noteText="Please insert your bills one at a time"
          />
        </div>

        {/* Right Panel - Counter */}
        <div className="flex-1 flex flex-col">
          {/* Heading */}
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center mb-6"
          >
            <h1 className={`text-2xl font-bold ${styles.text} mb-1`}>
              Please Insert Money
            </h1>
            <p className={`${styles.text} text-sm`}>
              Accepted: P20, P50, P100, P200, P500, P1000
            </p>
          </motion.div>

          {/* Current Count */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.1 }}
            className="text-center mb-4"
          >
            <p className="text-lg text-gray-600 mb-1">Current Count</p>
            <p className="text-6xl font-bold text-gray-900">
              P{ewallet.totalInserted}
            </p>
          </motion.div>

          {/* Total Due Badge */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="flex justify-center mb-6"
          >
            <span
              className={`${styles.bg} text-white px-4 py-2 rounded-full text-lg font-semibold`}
            >
              Total Due: P{ewallet.totalDue}
            </span>
          </motion.div>

          {/* Denomination Counters (ALL denominations per mockup) */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex justify-center gap-3 flex-wrap mb-6"
          >
            {EWALLET_ALL_DENOMINATIONS.map((denom) => {
              const billCount = ewallet.insertedBillCounts[denom] || 0;
              const coinCount = ewallet.insertedCoinCounts[denom] || 0;
              const count = billCount + coinCount;
              return (
                <div
                  key={denom}
                  className="text-center bg-gray-100 px-3 py-2 rounded-lg"
                >
                  <span className={`text-lg font-semibold ${styles.text}`}>
                    P{denom}
                  </span>
                  <span className="text-gray-600 ml-2">= {count}x</span>
                </div>
              );
            })}
          </motion.div>

          {/* Timer */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
            className="mt-auto"
          >
            <Timer
              seconds={EWALLET_TIMER_DURATIONS.INSERT_MONEY}
              onComplete={handleTimeout}
              showProgressBar={true}
              autoStart={true}
              color={ewallet.provider} // 'gcash' or 'maya'
            />
            <p className="text-center text-gray-500 text-sm mt-2">
              This tab will automatically close after 60s if no money is
              inserted.
            </p>
          </motion.div>
        </div>
      </div>
    </PageLayout>
  );
}
