import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import Button from "../../components/common/Button";
import TransactionFeeTable from "../../components/ewallet/TransactionFeeTable";
import { ROUTES, getEWalletRoute } from "../../constants/routes";
import { useEWallet } from "../../context/EWalletContext";
import { isCashOut } from "../../constants/ewalletData";

export default function EWalletFeeScreen() {
  const navigate = useNavigate();
  const { ewallet, getEWalletConfig, getProviderStyles } = useEWallet();
  const config = getEWalletConfig();
  const styles = getProviderStyles();

  if (!config) {
    navigate(ROUTES.EWALLET);
    return null;
  }

  const handleProceed = () => {
    navigate(getEWalletRoute(ROUTES.EWALLET_MOBILE, ewallet.serviceType));
  };

  const handleBack = () => {
    navigate(ROUTES.EWALLET_REMINDER);
  };

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: handleBack,
        subtitle: "Transaction Fee",
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
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-140px)] p-6">
        <motion.h1
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className={`text-3xl font-bold ${styles.text} mb-8`}
        >
          Transaction Fee
        </motion.h1>

        <TransactionFeeTable
          showCashOutNote={isCashOut(ewallet.serviceType)}
          colorVariant={ewallet.provider}
          className="mb-8"
        />

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          <Button
            variant={config.provider} // "gcash" or "maya"
            size="xl"
            onClick={handleProceed}
            className="min-w-[200px]"
          >
            Proceed
          </Button>
        </motion.div>
      </div>
    </PageLayout>
  );
}
