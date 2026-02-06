import { useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import ServiceCard from "../../components/transaction/ServiceCard";
import { ROUTES } from "../../constants/routes";
import {
  EWALLET_SERVICES,
  EWALLET_PROVIDERS_CONFIG,
} from "../../constants/ewalletData";
import { useEWallet } from "../../context/EWalletContext";

export default function EWalletServiceScreen() {
  const navigate = useNavigate();
  const { provider } = useParams();
  const { setServiceType } = useEWallet();

  const providerConfig = EWALLET_PROVIDERS_CONFIG[provider];
  const services = EWALLET_SERVICES[provider] || [];

  const handleSelectService = (serviceType) => {
    setServiceType(serviceType);
    navigate(ROUTES.EWALLET_REMINDER);
  };

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: () => navigate(ROUTES.EWALLET),
        subtitle: providerConfig?.name || "E-Wallet",
      }}
    >
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-140px)] py-4">
        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <p
            className={`${providerConfig?.textColor || "text-coinnect-ewallet"} text-xl mb-2`}
          >
            {providerConfig?.name}
          </p>
          <h1 className="text-3xl font-bold text-gray-900">
            Select Type of Service
          </h1>
        </motion.div>

        {/* Service cards */}
        <div className="grid grid-cols-2 gap-6 w-full max-w-3xl">
          {services.map((service, index) => (
            <motion.div
              key={service.type}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <ServiceCard
                icon={service.icon}
                title={service.name}
                color={providerConfig?.color || "bg-coinnect-ewallet"}
                onClick={() => handleSelectService(service.type)}
                className="h-full min-h-[220px]"
              />
            </motion.div>
          ))}
        </div>
      </div>
    </PageLayout>
  );
}
