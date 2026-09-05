import { motion } from "framer-motion";
import Button from "../common/Button";
import { formatPeso } from "../../constants/denominations";

export default function PayoutReapprovalModal({
  pendingQuote,
  onApprove,
  onRequestClaim,
  isLoading = false,
}) {
  if (!pendingQuote) return null;

  const items = pendingQuote.items || [];
  const bills = items.filter((i) => i.denom_type === "bill" || !i.denom_type);
  const coins = items.filter((i) => i.denom_type === "coin");

  return (
    <div className="fixed inset-0 bg-black/75 backdrop-blur-md flex items-center justify-center p-4 z-50">
      <motion.div
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        className="bg-white rounded-3xl p-8 max-w-lg w-full shadow-2xl border border-amber-300 text-center"
      >
        <div className="w-16 h-16 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4 text-amber-700 text-3xl font-black">
          !
        </div>

        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          Payout Adjustment Required
        </h2>

        <p className="text-gray-600 text-sm mb-4">
          Machine stock changed while accepting your payment. The previously approved payout breakdown is no longer available.
        </p>

        {pendingQuote.substitution_notice && (
          <div className="bg-amber-50 border border-amber-300 rounded-2xl p-4 mb-4 text-left">
            <p className="text-xs font-bold text-amber-800 uppercase tracking-wider mb-1">
              Revised Proposal Notice
            </p>
            <p className="text-sm text-amber-900 font-medium">
              {pendingQuote.substitution_notice}
            </p>
          </div>
        )}

        {/* Revised items breakdown */}
        <div className="bg-gray-50 border border-gray-200 rounded-2xl p-4 mb-6 text-left">
          <div className="flex justify-between items-center mb-3">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-500">
              Revised Dispense Breakdown
            </span>
            <span className="text-sm font-bold text-coinnect-primary">
              Total: {formatPeso(pendingQuote.payout_amount)}
            </span>
          </div>

          <div className="flex flex-wrap gap-2">
            {bills.map((item, idx) => (
              <div
                key={`b-${idx}-${item.value}`}
                className="bg-white border border-gray-300 px-3 py-1.5 rounded-xl text-sm font-bold text-gray-800 shadow-sm flex items-center gap-1.5"
              >
                <span className="text-xs bg-gray-200 text-gray-700 px-1.5 py-0.5 rounded font-mono">
                  Bill
                </span>
                {item.count}x {formatPeso(item.value)}
              </div>
            ))}
            {coins.map((item, idx) => (
              <div
                key={`c-${idx}-${item.value}`}
                className="bg-amber-100/60 border border-amber-300 px-3 py-1.5 rounded-xl text-sm font-bold text-amber-900 shadow-sm flex items-center gap-1.5"
              >
                <span className="text-xs bg-amber-300/60 text-amber-900 px-1.5 py-0.5 rounded font-mono">
                  Coin
                </span>
                {item.count}x {formatPeso(item.value)}
              </div>
            ))}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-col sm:flex-row gap-3">
          <Button
            variant="outline"
            size="lg"
            onClick={onRequestClaim}
            disabled={isLoading}
            className="flex-1 border-red-300 text-red-700 hover:bg-red-50 text-sm font-bold py-4"
          >
            Request Cash Claim
          </Button>

          <Button
            variant="primary"
            size="lg"
            onClick={() => onApprove(pendingQuote.id)}
            disabled={isLoading}
            className="flex-1 text-sm font-bold py-4 shadow-lg"
          >
            {isLoading ? "Approving..." : "Accept Revised Payout"}
          </Button>
        </div>

        <p className="text-xs text-gray-400 mt-4">
          A claim records the money owed to you, including the fee. Staff must settle the claim; cash is not dispensed here.
        </p>
      </motion.div>
    </div>
  );
}
