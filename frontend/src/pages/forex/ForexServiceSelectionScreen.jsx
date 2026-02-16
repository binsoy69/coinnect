import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../../components/layout/PageLayout";
import ServiceCard from "../../components/transaction/ServiceCard";
import { ROUTES } from "../../constants/routes";
import { FOREX_SERVICES } from "../../constants/forexData";
import { useForex } from "../../context/ForexContext";
import { useForexTransaction } from "../../hooks/useForexTransaction";

export default function ForexServiceSelectionScreen() {
  const navigate = useNavigate();
  const { startForexTransaction, updateRatesFromBackend } = useForex();
  const { checkConnectivity, isOnline, forexRates } = useForexTransaction();

  // Check connectivity and fetch rates on mount
  useEffect(() => {
    checkConnectivity();
  }, [checkConnectivity]);

  // Push backend rates into ForexContext
  useEffect(() => {
    if (forexRates && Object.keys(forexRates).length > 0) {
      updateRatesFromBackend(forexRates);
    }
  }, [forexRates, updateRatesFromBackend]);

  const handleSelectService = (serviceType) => {
    startForexTransaction(serviceType);
    navigate(ROUTES.FOREX_REMINDER);
  };

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: () => navigate(ROUTES.SELECT_TRANSACTION),
        subtitle: "Foreign Exchange",
        rightContent: !isOnline ? (
          <div className="flex items-center gap-2 bg-yellow-500 text-white px-3 py-1 rounded-full text-sm">
            <span className="w-2 h-2 bg-white rounded-full animate-pulse"></span>
            Offline - Using cached rates
          </div>
        ) : (
          <div className="flex items-center gap-2 bg-green-500 text-white px-3 py-1 rounded-full text-sm">
            <span className="w-2 h-2 bg-white rounded-full"></span>
            Live Rates
          </div>
        ),
      }}
    >
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-140px)] py-4">
        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <p className="text-coinnect-forex text-xl mb-2">Foreign Exchange</p>
          <h1 className="text-3xl font-bold text-gray-900">
            Select Type of Service
          </h1>
        </motion.div>

        {/* Service cards - 4 columns for forex */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full max-w-5xl">
          {FOREX_SERVICES.map((service, index) => (
            <motion.div
              key={service.type}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <ServiceCard
                icon={service.icon}
                title={service.title}
                color="bg-coinnect-forex"
                onClick={() => handleSelectService(service.type)}
                className="h-full min-h-[180px]"
              />
            </motion.div>
          ))}
        </div>
      </div>
    </PageLayout>
  );
}
