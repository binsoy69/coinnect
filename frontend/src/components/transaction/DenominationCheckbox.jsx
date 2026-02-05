import { motion } from 'framer-motion';
import { Check } from 'lucide-react';
import { DENOMINATION_DISPLAY } from '../../constants/denominations';

export default function DenominationCheckbox({
  denominations = [],
  selectedValues = [],
  onToggle,
  disabledValues = [],
  columns = 3,
  className = '',
}) {
  const gridCols = {
    2: 'grid-cols-2',
    3: 'grid-cols-3',
    4: 'grid-cols-4',
  };

  return (
    <div className={`grid ${gridCols[columns] || 'grid-cols-3'} gap-4 ${className}`}>
      {denominations.map((denom) => {
        const isSelected = selectedValues.includes(denom);
        const isDisabled = disabledValues.includes(denom);

        return (
          <motion.button
            key={denom}
            onClick={() => !isDisabled && onToggle?.(denom)}
            whileHover={isDisabled ? {} : { scale: 1.02 }}
            whileTap={isDisabled ? {} : { scale: 0.98 }}
            disabled={isDisabled}
            className={`
              flex items-center gap-4 p-4 rounded-card
              border-2 transition-all duration-200
              ${isSelected
                ? 'border-coinnect-primary bg-coinnect-primary/5'
                : 'border-gray-300 bg-white'
              }
              ${isDisabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
            `}
          >
            {/* Checkbox */}
            <div
              className={`
                w-6 h-6 rounded border-2 flex items-center justify-center
                transition-all duration-200
                ${isSelected
                  ? 'bg-coinnect-primary border-coinnect-primary'
                  : 'border-gray-400 bg-white'
                }
              `}
            >
              {isSelected && <Check className="w-4 h-4 text-white" />}
            </div>

            {/* Denomination label */}
            <span className={`text-2xl font-bold ${isSelected ? 'text-coinnect-primary' : 'text-gray-700'}`}>
              {DENOMINATION_DISPLAY[denom] || `P${denom}`}
            </span>
          </motion.button>
        );
      })}
    </div>
  );
}
