import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import VirtualKeyboard from "../../components/common/VirtualKeyboard";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";

export default function EWalletNameScreen() {
  const navigate = useNavigate();
  const {
    ewallet,
    setAccountName,
    getEWalletConfig,
    getProviderStyles,
  } = useEWallet();
  const config = getEWalletConfig();
  const styles = getProviderStyles();
  const [accountName, setAccountNameValue] = useState(
    ewallet.accountName || "",
  );

  if (!config) {
    navigate(ROUTES.EWALLET);
    return null;
  }

  const handleSubmit = (name) => {
    if (name.trim().length < 2) return;
    setAccountName(name.trim());
    navigate(getEWalletRoute(ROUTES.EWALLET_MOBILE, ewallet.serviceType));
  };

  const handleBack = () => {
    navigate(getEWalletRoute(ROUTES.EWALLET_FEE, ewallet.serviceType));
  };

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: handleBack,
        subtitle: "Enter Account Name",
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
          Enter Account Name
        </motion.h1>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="w-full max-w-xl"
        >
          <label className="block mb-5">
            <span className="block text-sm font-semibold text-gray-600 mb-2">
              Account Name
            </span>
            <input
              type="text"
              value={accountName}
              readOnly={true}
              placeholder="Name registered to the wallet"
              className={`w-full border-2 rounded-xl px-4 py-3 text-lg outline-none ${styles.text} bg-gray-50 focus:ring-2 focus:ring-blue-200 cursor-default`}
            />
          </label>
          <VirtualKeyboard
            value={accountName}
            onChange={setAccountNameValue}
            onSubmit={handleSubmit}
            maxLength={120}
            placeholder="ENTER FULL NAME"
            submitLabel="Proceed"
            colorClass={`coinnect-${ewallet.provider}`}
          />
        </motion.div>
      </div>
    </PageLayout>
  );
}
