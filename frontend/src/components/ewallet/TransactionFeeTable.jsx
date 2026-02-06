import { motion } from "framer-motion";
import { EWALLET_FEE_TIERS } from "../../constants/ewalletData";

export default function TransactionFeeTable({
  feeTiers = EWALLET_FEE_TIERS,
  showCashOutNote = false,
  className = "",
  colorVariant = "ewallet", // 'gcash' or 'maya'
}) {
  const bgColor =
    colorVariant === "maya"
      ? "bg-coinnect-maya"
      : colorVariant === "gcash"
        ? "bg-coinnect-gcash"
        : "bg-coinnect-ewallet";
  const borderColor =
    colorVariant === "maya"
      ? "border-coinnect-maya"
      : colorVariant === "gcash"
        ? "border-coinnect-gcash"
        : "border-coinnect-ewallet";
  const rowBorder =
    colorVariant === "maya"
      ? "border-green-400"
      : colorVariant === "gcash"
        ? "border-blue-400"
        : "border-blue-400";
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`w-full max-w-xl ${className}`}
    >
      {/* Table */}
      <div
        className={`w-full overflow-hidden rounded-xl border-2 ${borderColor}`}
      >
        {/* Header */}
        <div className="grid grid-cols-2 bg-gray-100">
          <div className="p-3 text-center text-sm font-semibold text-gray-600">
            Amount
          </div>
          <div className="p-3 text-center text-sm font-semibold text-gray-600">
            Transaction Fee
          </div>
        </div>

        {/* Fee tiers */}
        {feeTiers.map((tier, index) => (
          <motion.div
            key={index}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.15 }}
            className={`grid grid-cols-2 ${bgColor} text-white border-t ${rowBorder}`}
          >
            <div className="p-4 text-center text-xl font-bold">
              P{tier.min} - P{tier.max}
            </div>
            <div className="p-4 text-center text-xl font-bold">P{tier.fee}</div>
          </motion.div>
        ))}
      </div>

      {/* Notes */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
        className="mt-6 text-center"
      >
        <p className="text-lg font-semibold text-gray-800">
          <span className="font-bold italic">Note:</span> The transaction fee is
          automatically deducted from the inserted amount.
        </p>
        {showCashOutNote && (
          <p className="text-lg font-semibold text-gray-800 mt-3">
            <span className="font-bold italic">Note:</span> Ensure you have your
            mobile phone and the provided mobile number with you.
          </p>
        )}
      </motion.div>
    </motion.div>
  );
}
