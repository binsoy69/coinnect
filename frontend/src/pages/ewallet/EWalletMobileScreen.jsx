import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import VirtualKeypad from "../../components/common/VirtualKeypad";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";

export default function EWalletMobileScreen() {
  const navigate = useNavigate();
  const { ewallet, setMobileNumber, getEWalletConfig, getProviderStyles } =
    useEWallet();
  const config = getEWalletConfig();
  const styles = getProviderStyles();
  const [value, setValue] = useState("");

  if (!config) {
    navigate(ROUTES.EWALLET);
    return null;
  }

  const handleSubmit = (mobile) => {
    setMobileNumber(mobile);
    navigate(getEWalletRoute(ROUTES.EWALLET_AMOUNT, ewallet.serviceType));
  };

  const handleBack = () => {
    navigate(getEWalletRoute(ROUTES.EWALLET_FEE, ewallet.serviceType));
  };

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: handleBack,
        subtitle: "Enter Mobile Number",
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
          Enter Mobile Number
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
            maxLength={11}
            placeholder="09XXXXXXXXX"
            submitLabel="Proceed"
            colorClass={`coinnect-${ewallet.provider}`}
          />
        </motion.div>
      </div>
    </PageLayout>
  );
}
