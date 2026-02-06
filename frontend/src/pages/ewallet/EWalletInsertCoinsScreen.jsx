import { useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import InsertMoneyPanel from "../../components/transaction/InsertMoneyPanel";
import Timer from "../../components/common/Timer";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";
import {
  EWALLET_COIN_DENOMINATIONS,
  EWALLET_TIMER_DURATIONS,
} from "../../constants/ewalletData";

export default function EWalletInsertCoinsScreen() {
  const navigate = useNavigate();
  const {
    ewallet,
    addInsertedCoin,
    getEWalletConfig,
    getProviderStyles,
    isAmountMatched,
    getRemainingAmount,
  } = useEWallet();
  const config = getEWalletConfig();
  const styles = getProviderStyles();

  // Handle timeout - go to details even if partial
  const handleTimeout = useCallback(() => {
    navigate(getEWalletRoute(ROUTES.EWALLET_DETAILS, ewallet.serviceType));
  }, [navigate, ewallet.serviceType]);

  // Keyboard simulation for testing (keys 1-4 = coin denominations)
  useEffect(() => {
    const handleKeyPress = (e) => {
      const keyMap = {
        1: EWALLET_COIN_DENOMINATIONS[0], // P1
        2: EWALLET_COIN_DENOMINATIONS[1], // P5
        3: EWALLET_COIN_DENOMINATIONS[2], // P10
        4: EWALLET_COIN_DENOMINATIONS[3], // P20
      };

      if (keyMap[e.key]) {
        addInsertedCoin(keyMap[e.key]);
      }
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [addInsertedCoin]);

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

  const remainingAmount = getRemainingAmount();

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: () =>
          navigate(
            getEWalletRoute(ROUTES.EWALLET_INSERT_BILLS, ewallet.serviceType),
          ),
        subtitle: "Insert Coins",
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
            variant="coin"
            cardVariant={ewallet.provider} // 'gcash' or 'maya'
            noteText="Please insert your coins one at a time"
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
              Please Insert Coins
            </h1>
            <p className={`${styles.text} text-sm`}>
              Accepted: P1, P5, P10, P20
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

          {/* Remaining Amount Badge */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="flex justify-center gap-4 mb-6"
          >
            <span
              className={`${styles.bg} text-white px-4 py-2 rounded-full text-lg font-semibold`}
            >
              Total Due: P{ewallet.totalDue}
            </span>
            {remainingAmount > 0 && (
              <span className="bg-orange-500 text-white px-4 py-2 rounded-full text-lg font-semibold">
                Remaining: P{remainingAmount}
              </span>
            )}
          </motion.div>

          {/* Coin Denomination Counters */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="flex justify-center gap-4 flex-wrap mb-6"
          >
            {EWALLET_COIN_DENOMINATIONS.map((denom) => {
              const count = ewallet.insertedCoinCounts[denom] || 0;
              return (
                <div
                  key={denom}
                  className="text-center bg-gray-100 px-4 py-2 rounded-lg"
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
              This tab will automatically close after 60s if no coins are
              inserted.
            </p>
          </motion.div>
        </div>
      </div>
    </PageLayout>
  );
}
