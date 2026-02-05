import { motion } from "framer-motion";
import PropTypes from "prop-types";
import { CURRENCY_SYMBOLS } from "../../constants/forexData";

/**
 * CurrencyAmountGrid - Grid of currency amount selection buttons
 * Displays amounts with currency symbol (€5, €10, $10, etc.)
 */
function CurrencyAmountGrid({
  amounts = [],
  currency = "USD",
  selectedAmount = null,
  onSelect,
  disabled = false,
  className = "",
}) {
  const symbol = CURRENCY_SYMBOLS[currency] || "$";

  return (
    <div className={`grid grid-cols-3 gap-4 ${className}`}>
      {amounts.map((amount) => {
        const isSelected = selectedAmount === amount;

        return (
          <motion.button
            key={amount}
            onClick={() => onSelect?.(amount)}
            disabled={disabled}
            whileHover={disabled ? {} : { scale: 1.02 }}
            whileTap={disabled ? {} : { scale: 0.98 }}
            className={`
              p-6 rounded-card text-4xl font-bold
              transition-all duration-200
              ${
                isSelected
                  ? "bg-coinnect-forex text-white border-2 border-coinnect-forex"
                  : "bg-white border-2 border-coinnect-forex text-coinnect-forex hover:bg-coinnect-forex/5"
              }
              ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
            `}
          >
            {symbol}
            {amount}
          </motion.button>
        );
      })}
    </div>
  );
}

CurrencyAmountGrid.propTypes = {
  amounts: PropTypes.arrayOf(PropTypes.number),
  currency: PropTypes.string,
  selectedAmount: PropTypes.number,
  onSelect: PropTypes.func,
  disabled: PropTypes.bool,
  className: PropTypes.string,
};

export default CurrencyAmountGrid;
