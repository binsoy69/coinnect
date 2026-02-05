import { motion } from "framer-motion";
import { DENOMINATION_DISPLAY } from "../../constants/denominations";

export default function DenominationGrid({
  denominations = [],
  selectedValue = null,
  onSelect,
  disabled = false,
  className = "",
}) {
  return (
    <div className={`flex flex-wrap justify-center gap-8 ${className}`}>
      {denominations.map((denom) => {
        const isSelected = selectedValue === denom;

        return (
          <motion.button
            key={denom}
            onClick={() => !disabled && onSelect?.(denom)}
            whileHover={disabled ? {} : { scale: 1.05 }}
            whileTap={disabled ? {} : { scale: 0.95 }}
            disabled={disabled}
            className={`
              p-8 rounded-[2rem] text-5xl font-bold min-w-[200px]
              border-4 transition-all duration-200
              touch-target-lg flex items-center justify-center
              ${
                isSelected
                  ? "bg-coinnect-primary text-white border-coinnect-primary"
                  : "bg-white text-coinnect-primary border-coinnect-primary"
              }
              ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
            `}
          >
            {denom}
          </motion.button>
        );
      })}
    </div>
  );
}
