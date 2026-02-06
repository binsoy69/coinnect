import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import VirtualKeypad from "../../components/common/VirtualKeypad";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";

export default function EWalletVerifyPINScreen() {
  const navigate = useNavigate();
  const { ewallet, setVerificationPIN, getEWalletConfig, getProviderStyles } =
    useEWallet();
  const config = getEWalletConfig();
  const styles = getProviderStyles();
  const [value, setValue] = useState("");

  if (!config) {
    navigate(ROUTES.EWALLET);
    return null;
  }

  const handleSubmit = (pin) => {
    setVerificationPIN(pin);
    // Accept any PIN for demo purposes
    navigate(getEWalletRoute(ROUTES.EWALLET_DETAILS, ewallet.serviceType));
  };

  const handleBack = () => {
    navigate(getEWalletRoute(ROUTES.EWALLET_QR, ewallet.serviceType));
  };

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: handleBack,
        subtitle: "Verify Transaction",
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
          className={`text-2xl lg:text-3xl font-bold ${styles.text} mb-2`}
        >
          Enter Verification PIN
        </motion.h1>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="text-gray-500 mb-4 lg:mb-8 text-sm lg:text-base"
        >
          Enter the 6-digit PIN sent to your mobile number
        </motion.p>

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
            maxLength={6}
            placeholder="******"
            submitLabel="Verify"
            colorClass={`coinnect-${ewallet.provider}`}
          />
        </motion.div>
      </div>
    </PageLayout>
  );
}
