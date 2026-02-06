import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import ServiceCard from "../../components/transaction/ServiceCard";
import { ROUTES, getEWalletProviderRoute } from "../../constants/routes";
import {
  EWALLET_PROVIDER_LIST,
  EWALLET_PROVIDERS_CONFIG,
} from "../../constants/ewalletData";
import { useEWallet } from "../../context/EWalletContext";

export default function EWalletProviderScreen() {
  const navigate = useNavigate();
  const { startEWalletTransaction } = useEWallet();

  const handleSelectProvider = (provider) => {
    startEWalletTransaction(provider.id);
    navigate(getEWalletProviderRoute(ROUTES.EWALLET_SERVICE, provider.id));
  };

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: () => navigate(ROUTES.SELECT_TRANSACTION),
        subtitle: "E-Wallet",
      }}
    >
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-140px)] py-4">
        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <p className="text-coinnect-ewallet text-xl mb-2">E-Wallet</p>
          <h1 className="text-3xl font-bold text-gray-900">
            Select your E-Wallet
          </h1>
        </motion.div>

        {/* Provider cards */}
        <div className="grid grid-cols-2 gap-6 w-full max-w-3xl">
          {EWALLET_PROVIDER_LIST.map((provider, index) => (
            <motion.div
              key={provider.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <ServiceCard
                icon={provider.icon}
                title={provider.name}
                color={EWALLET_PROVIDERS_CONFIG[provider.id].color}
                onClick={() => handleSelectProvider(provider)}
                className="h-full min-h-[220px]"
              />
            </motion.div>
          ))}
        </div>
      </div>
    </PageLayout>
  );
}
