import { motion } from 'framer-motion';
import PropTypes from 'prop-types';

// Flag components using emoji or simple text representations
const FLAGS = {
  us: '🇺🇸',
  ph: '🇵🇭',
  eu: '🇪🇺',
};

/**
 * ExchangeRateCard - Displays live exchange rate with flag
 * Shows: Flag | Country Name | Currency Code | Rate in PHP
 */
function ExchangeRateCard({
  flag = 'us',
  countryName = 'UNITED STATES',
  currencyCode = 'USD',
  rate = 0,
  targetCurrency = 'PHP',
  className = '',
}) {
  // Format rate to 4 decimal places
  const formattedRate = rate.toFixed(4);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`
        bg-coinnect-forex rounded-card p-4 px-6
        flex items-center justify-between
        text-white
        ${className}
      `}
    >
      {/* Flag and Country */}
      <div className="flex items-center gap-4">
        <span className="text-4xl" role="img" aria-label={`${countryName} flag`}>
          {FLAGS[flag] || '🏳️'}
        </span>
        <span className="text-xl font-semibold tracking-wide">
          {countryName}
        </span>
      </div>

      {/* Currency Code */}
      <span className="text-xl font-medium">
        {currencyCode}
      </span>

      {/* Rate */}
      <span className="text-xl font-bold">
        {formattedRate} {targetCurrency}
      </span>
    </motion.div>
  );
}

ExchangeRateCard.propTypes = {
  flag: PropTypes.oneOf(['us', 'ph', 'eu']),
  countryName: PropTypes.string,
  currencyCode: PropTypes.string,
  rate: PropTypes.number,
  targetCurrency: PropTypes.string,
  className: PropTypes.string,
};

export default ExchangeRateCard;
