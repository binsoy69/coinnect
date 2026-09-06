import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import VirtualKeypad from "../../components/common/VirtualKeypad";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";
import { isCashOut } from "../../constants/ewalletData";

export default function EWalletAmountScreen() {
  const navigate = useNavigate();
  const { ewallet, obtainQuote, getEWalletConfig, getProviderStyles } =
    useEWallet();
  const config = getEWalletConfig();
  const styles = getProviderStyles();
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(false);

  if (!config) {
    navigate(ROUTES.EWALLET);
    return null;
  }

  const handleSubmit = async (amountStr) => {
    if (checking) return;
    const amount = parseInt(amountStr, 10);
    setChecking(true);
    try {
      await obtainQuote(amount);
      navigate(getEWalletRoute(isCashOut(ewallet.serviceType) ? ROUTES.EWALLET_CONFIRM : ROUTES.EWALLET_NAME, ewallet.serviceType));
    } catch (failure) { setError(failure.message); }
    finally { setChecking(false); }
  };

  const handleBack = () => {
    const previousRoute = ROUTES.EWALLET_FEE;
    navigate(getEWalletRoute(previousRoute, ewallet.serviceType));
  };

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: handleBack,
        subtitle: "Enter Amount",
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
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-100px)] p-4 lg:p-6">
        <motion.h1
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className={`text-2xl lg:text-3xl font-bold ${styles.text} mb-4 lg:mb-8`}
        >
          Enter Amount
        </motion.h1>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="w-full max-w-xl"
        >
          <VirtualKeypad
            value={value}
            onChange={setValue}
            onSubmit={handleSubmit}
            maxLength={5}
            placeholder="0000"
            submitLabel={checking ? "Checking inventory…" : "Check availability"}
            colorClass={`coinnect-${ewallet.provider}`}
          />
          <p className="mt-4 text-center">Enter the total you will pay. The fee is deducted from this amount.</p>
          {error && <p role="alert" className="mt-4 text-center text-red-700">{error}</p>}
        </motion.div>
      </div>
    </PageLayout>
  );
}
