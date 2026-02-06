import { motion } from "framer-motion";
import Clock from "../common/Clock";
import Button from "../common/Button";
import { formatPeso } from "../../constants/denominations";

export default function AccountDetailsPanel({
  moneyInserted = 0,
  fee = 0,
  billerNumber = "",
  mobileNumber = "",
  transferAmount = 0,
  providerName = "GCash",
  isCashOut = false,
  onProceed,
  className = "",
  colorVariant = "gcash", // 'gcash' or 'maya'
}) {
  const bgColorClass =
    colorVariant === "maya" ? "bg-coinnect-maya" : "bg-coinnect-gcash";
  const buttonVariant = colorVariant;
  return (
    <div
      className={`grid grid-cols-1 md:grid-cols-3 gap-6 w-full ${className}`}
    >
      {/* Left: Blue summary card */}
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        className={`${bgColorClass} text-white rounded-card p-6 flex flex-col justify-between`}
      >
        <div>
          <p className="text-sm font-semibold opacity-80 mb-1">
            {isCashOut ? "Money Send" : "Money Inserted"}
          </p>
          <p className="text-4xl font-bold mb-4">{formatPeso(moneyInserted)}</p>

          <p className="text-sm font-semibold opacity-80 mb-1">
            Transaction Fee
          </p>
          <p className="text-3xl font-bold mb-4">{formatPeso(fee)}</p>
        </div>

        <div className="border-t border-white/30 pt-4 mt-auto">
          <Clock variant="light" />
        </div>
      </motion.div>

      {/* Right: Account details */}
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: 0.1 }}
        className="md:col-span-2 flex flex-col"
      >
        <h2 className="text-2xl font-bold text-gray-900 mb-6">
          Account Details
        </h2>

        <div className="grid grid-cols-2 gap-x-8 gap-y-4 mb-8">
          <div>
            <p className="text-sm font-bold italic text-gray-600 mb-1">
              Biller
            </p>
            <p className="text-lg font-semibold text-gray-900">
              {providerName.toUpperCase()}
            </p>
          </div>
          <div>
            <p className="text-sm font-bold italic text-gray-600 mb-1">
              My Mobile Number
            </p>
            <p className="text-lg font-semibold text-gray-900">
              {mobileNumber}
            </p>
          </div>
          <div>
            <p className="text-sm font-bold italic text-gray-600 mb-1">
              Mobile Number
            </p>
            <p className="text-lg font-semibold text-gray-900">
              {billerNumber}
            </p>
          </div>
          <div>
            <p className="text-sm font-bold italic text-gray-600 mb-1">
              Amount to Transfer
            </p>
            <p className="text-lg font-semibold text-gray-900">
              {formatPeso(transferAmount)}
            </p>
          </div>
        </div>

        {/* Proceed button */}
        <div className="flex justify-end mt-auto">
          <Button variant={buttonVariant} size="lg" onClick={onProceed}>
            Proceed
          </Button>
        </div>
      </motion.div>
    </div>
  );
}
