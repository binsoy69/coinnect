import { motion } from "framer-motion";
import { DENOMINATION_DISPLAY } from "../../constants/denominations";

export default function DenominationGrid({
  denominations = [],
  selectedValue = null,
  onSelect,
  disabled = false,
  disabledValues = [],
  reasonsMap = {},
  className = "",
}) {
  return (
    <div className={`flex flex-wrap justify-center gap-8 ${className}`}>
      {denominations.map((denom) => {
        const isSelected = selectedValue === denom;
        const isItemDisabled =
          disabled || (Array.isArray(disabledValues) && disabledValues.includes(denom));
        const reason = reasonsMap?.[denom];

        return (
          <motion.button
            key={denom}
            type="button"
            onClick={() => !isItemDisabled && onSelect?.(denom)}
            whileHover={isItemDisabled ? {} : { scale: 1.05 }}
            whileTap={isItemDisabled ? {} : { scale: 0.95 }}
            disabled={isItemDisabled}
            className={`
              p-6 rounded-[2rem] text-5xl font-bold min-w-[200px] min-h-[130px]
              border-4 transition-all duration-200
              touch-target-lg flex flex-col items-center justify-center
              ${
                isItemDisabled
                  ? "bg-gray-100 text-gray-400 border-gray-300 opacity-50 cursor-not-allowed"
                  : isSelected
                  ? "bg-coinnect-primary text-white border-coinnect-primary cursor-pointer shadow-lg"
                  : "bg-white text-coinnect-primary border-coinnect-primary cursor-pointer hover:shadow-md"
              }
            `}
          >
            <span>{denom}</span>
            {isItemDisabled && reason && (
              <span className="text-xs font-medium text-amber-700 mt-1 max-w-[170px] text-center leading-tight">
                {reason}
              </span>
            )}
          </motion.button>
        );
      })}
    </div>
  );
}
