import { motion } from 'framer-motion';
import PropTypes from 'prop-types';
import { formatCurrency } from '../../constants/forexData';

/**
 * ConversionDisplay - Shows conversion table with Amount | From | To
 * Displays the conversion calculation in a table format
 */
function ConversionDisplay({
  fromAmount,
  fromCurrency,
  toAmount,
  toCurrency,
  showHeader = true,
  note = 'Centavos are not included for dispensing.',
  className = '',
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`bg-white rounded-card overflow-hidden ${className}`}
    >
      {/* Table */}
      <table className="w-full">
        {showHeader && (
          <thead>
            <tr className="border-b border-gray-200">
              <th className="p-4 text-left text-lg font-semibold text-gray-700">
                Amount
              </th>
              <th className="p-4 text-center text-lg font-semibold text-gray-700">
                From
              </th>
              <th className="p-4 text-right text-lg font-semibold text-gray-700">
                To
              </th>
            </tr>
          </thead>
        )}
        <tbody>
          <tr>
            <td className="p-4 text-left">
              <span className="text-2xl font-bold text-coinnect-forex">
                {formatCurrency(fromAmount, fromCurrency)}
              </span>
            </td>
            <td className="p-4 text-center">
              <span className="text-xl font-semibold text-gray-600">
                {fromCurrency}
              </span>
            </td>
            <td className="p-4 text-right">
              <span className="text-2xl font-bold text-coinnect-forex">
                {formatCurrency(toAmount, toCurrency)}
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      {/* Note */}
      {note && (
        <p className="px-4 pb-4 text-sm text-gray-500 italic">
          {note}
        </p>
      )}
    </motion.div>
  );
}

ConversionDisplay.propTypes = {
  fromAmount: PropTypes.number.isRequired,
  fromCurrency: PropTypes.string.isRequired,
  toAmount: PropTypes.number.isRequired,
  toCurrency: PropTypes.string.isRequired,
  showHeader: PropTypes.bool,
  note: PropTypes.string,
  className: PropTypes.string,
};

export default ConversionDisplay;
