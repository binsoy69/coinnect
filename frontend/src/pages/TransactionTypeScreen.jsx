import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import PageLayout from "../components/layout/PageLayout";
import ServiceCard from "../components/transaction/ServiceCard";
import { ROUTES } from "../constants/routes";
import { TRANSACTION_TYPES } from "../constants/mockData";

export default function TransactionTypeScreen() {
  const navigate = useNavigate();

  const handleSelectType = (type) => {
    if (!type.enabled) return;

    if (type.id === "converter") {
      navigate(ROUTES.MONEY_CONVERTER);
    } else if (type.id === "forex") {
      navigate(ROUTES.FOREX);
    } else if (type.id === "ewallet") {
      navigate(ROUTES.EWALLET);
    }
  };

  return (
    <PageLayout
      headerProps={{
        showBack: true,
        onBack: () => navigate(ROUTES.HOME),
      }}
    >
      <div className="flex flex-col items-center justify-center min-h-[calc(100vh-140px)] py-4">
        {/* Heading */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <p className="text-gray-500 text-lg italic mb-1">Hello!</p>
          <h1 className="text-3xl font-bold text-gray-900">
            Select Type of Transaction
          </h1>
        </motion.div>

        {/* Service cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full max-w-5xl">
          {TRANSACTION_TYPES.map((type, index) => (
            <motion.div
              key={type.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <ServiceCard
                icon={type.icon}
                title={type.name}
                description={type.description}
                color={type.bgClass}
                disabled={!type.enabled}
                onClick={() => handleSelectType(type)}
                className="h-full min-h-[220px]"
              />
            </motion.div>
          ))}
        </div>
      </div>
    </PageLayout>
  );
}
