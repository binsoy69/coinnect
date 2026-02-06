import { motion } from "framer-motion";
import Button from "../common/Button";
import { formatPeso } from "../../constants/denominations";

import {
  EWALLET_PROVIDERS,
  EWALLET_PROVIDERS_CONFIG,
} from "../../constants/ewalletData";

export default function EWalletTransactionCard({
  serviceName = "",
  mobileNumber = "",
  totalInserted = 0,
  fee = 0,
  transferAmount = 0,
  totalDue = 0,
  onBack,
  onProceed,
  className = "",
  provider = null,
}) {
  const providerConfig = provider ? EWALLET_PROVIDERS_CONFIG[provider] : null;
  const bgColor = providerConfig?.color || "bg-coinnect-ewallet";

  // Determine button variant based on provider
  let buttonVariant = "white";
  if (provider === EWALLET_PROVIDERS.GCASH) buttonVariant = "white-blue";
  if (provider === EWALLET_PROVIDERS.MAYA) buttonVariant = "white-green";

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
      className={`${bgColor} rounded-card p-8 max-w-md w-full text-white text-center ${className}`}
    >
      {/* Header */}
      <h2 className="text-2xl font-bold italic mb-1">MY TRANSACTION</h2>
      <p className="text-sm text-white/70 mb-6">
        Please review the information below
      </p>

      {/* Transaction Type */}
      <div className="mb-3">
        <p className="text-xs font-semibold text-white/70">Transaction Type</p>
        <p className="text-xl font-bold">E-Wallet</p>
      </div>

      {/* Service Type */}
      <div className="mb-3">
        <p className="text-xs font-semibold text-white/70">Service Type</p>
        <p className="text-xl font-bold">{serviceName}</p>
      </div>

      {/* Mobile Number */}
      <div className="mb-4">
        <p className="text-xs font-semibold text-white/70">Mobile Number</p>
        <p className="text-3xl font-bold">{mobileNumber}</p>
      </div>

      {/* Amount grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 mb-6">
        <div>
          <p className="text-xs font-semibold text-white/70">
            Total Money Inserted
          </p>
          <p className="text-2xl font-bold">{formatPeso(totalInserted)}</p>
        </div>
        <div>
          <p className="text-xs font-semibold text-white/70">Transaction Fee</p>
          <p className="text-2xl font-bold">{formatPeso(fee)}</p>
        </div>
        <div>
          <p className="text-xs font-semibold text-white/70">
            Money to Transfer
          </p>
          <p className="text-2xl font-bold">{formatPeso(transferAmount)}</p>
        </div>
        <div>
          <p className="text-xs font-semibold text-white/70">Total Due</p>
          <p className="text-2xl font-bold">{formatPeso(totalDue)}</p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-4 justify-center">
        <Button variant="outline" size="lg" onClick={onBack}>
          Back
        </Button>
        <Button variant={buttonVariant} size="lg" onClick={onProceed}>
          Proceed
        </Button>
      </div>
    </motion.div>
  );
}
