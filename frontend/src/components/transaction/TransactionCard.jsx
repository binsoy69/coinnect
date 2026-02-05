import Card from "../common/Card";
import Button from "../common/Button";
import {
  formatPeso,
  DENOMINATION_DISPLAY,
} from "../../constants/denominations";
import { TRANSACTION_TYPE_LABEL } from "../../constants/mockData";

export default function TransactionCard({
  serviceType = "",
  serviceName = "",
  moneyInserted = 0,
  totalDue = 0,
  moneyToDispense = 0,
  selectedDenominations = [],
  showActions = true,
  onBack,
  onProceed,
  className = "",
}) {
  return (
    <Card
      variant="orange"
      animated={false}
      className={`p-5 max-w-lg mx-auto ${className}`}
    >
      {/* Header */}
      <div className="text-center mb-3">
        <h2 className="text-xl font-bold">MY TRANSACTION</h2>
        <p className="text-white/80 text-xs">Review your transaction details</p>
      </div>

      {/* Transaction Details */}
      <div className="space-y-2">
        {/* Transaction Type */}
        <div className="flex justify-between items-center py-1 border-b border-white/20">
          <span className="text-white/80 text-sm">Transaction Type</span>
          <span className="font-semibold text-sm">
            {TRANSACTION_TYPE_LABEL}
          </span>
        </div>

        {/* Service Type */}
        <div className="flex justify-between items-center py-1 border-b border-white/20">
          <span className="text-white/80 text-sm">Service Type</span>
          <span className="font-semibold text-sm">
            {serviceName || serviceType}
          </span>
        </div>

        {/* Combined Grid for Money Details */}
        <div className="grid grid-cols-2 gap-3 py-2">
          {/* Total Money Inserted */}
          <div className="text-center p-3 bg-white/10 rounded-lg">
            <p className="text-white/80 text-xs mb-1">Total Money Inserted</p>
            <p className="text-xl font-bold">{formatPeso(moneyInserted)}</p>
          </div>

          {/* Total Due */}
          <div className="text-center p-3 bg-white/10 rounded-lg">
            <p className="text-white/80 text-xs mb-1">Total Due</p>
            <p className="text-xl font-bold">{formatPeso(totalDue)}</p>
          </div>

          {/* Money to Dispense */}
          <div className="text-center p-3 bg-white/10 rounded-lg">
            <p className="text-white/80 text-xs mb-1">Money to Dispense</p>
            <p className="text-xl font-bold">{formatPeso(moneyToDispense)}</p>
          </div>

          {/* Selected Denominations */}
          <div className="text-center p-3 bg-white/10 rounded-lg flex flex-col justify-center">
            <p className="text-white/80 text-xs mb-1">Selected Denomination</p>
            <p className="text-base font-bold leading-tight">
              {selectedDenominations.length > 0
                ? selectedDenominations
                    .map((d) => DENOMINATION_DISPLAY[d] || `P${d}`)
                    .join(", ")
                : "None"}
            </p>
          </div>
        </div>
      </div>

      {/* Actions */}
      {showActions && (
        <div className="flex gap-3 mt-4">
          <Button
            variant="outline"
            onClick={onBack}
            className="flex-1 py-3 text-sm"
          >
            Back
          </Button>
          <Button
            variant="white"
            onClick={onProceed}
            className="flex-1 py-3 text-sm"
          >
            Proceed
          </Button>
        </div>
      )}
    </Card>
  );
}
