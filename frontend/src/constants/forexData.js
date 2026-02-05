import { FOREX_SERVICE_TYPES } from './routes';

// Currency codes
export const CURRENCIES = {
  PHP: 'PHP',
  USD: 'USD',
  EUR: 'EUR',
};

// Currency symbols
export const CURRENCY_SYMBOLS = {
  PHP: '₱',
  USD: '$',
  EUR: '€',
};

// Currency denominations per hardware spec
export const FOREX_DENOMINATIONS = {
  USD: [10, 50, 100],      // USD bills accepted/dispensed
  EUR: [5, 10, 20],        // EUR bills accepted/dispensed
  PHP: [20, 50, 100, 200, 500, 1000], // PHP bills
};

// Amount options for selection (what user can choose to convert)
export const FOREX_AMOUNT_OPTIONS = {
  [FOREX_SERVICE_TYPES.USD_TO_PHP]: [5, 10, 100],    // Select USD amount to convert
  [FOREX_SERVICE_TYPES.PHP_TO_USD]: [5, 10, 100],    // Select USD amount to receive
  [FOREX_SERVICE_TYPES.EUR_TO_PHP]: [5, 10, 20],     // Select EUR amount to convert
  [FOREX_SERVICE_TYPES.PHP_TO_EUR]: [5, 10, 100],    // Select EUR amount to receive
};

// Mock exchange rates (will be replaced by real API)
export const MOCK_EXCHANGE_RATES = {
  USD: 58.7656,  // 1 USD = 58.7656 PHP
  EUR: 61.7246,  // 1 EUR = 61.7246 PHP
};

// Service configuration for each forex type
export const FOREX_CONFIG = {
  [FOREX_SERVICE_TYPES.USD_TO_PHP]: {
    name: 'USD-to-PHP',
    displayName: 'USD to PHP',
    fromCurrency: CURRENCIES.USD,
    toCurrency: CURRENCIES.PHP,
    fromSymbol: CURRENCY_SYMBOLS.USD,
    toSymbol: CURRENCY_SYMBOLS.PHP,
    acceptDenominations: FOREX_DENOMINATIONS.USD,
    dispenseDenominations: FOREX_DENOMINATIONS.PHP,
    amountOptions: FOREX_AMOUNT_OPTIONS[FOREX_SERVICE_TYPES.USD_TO_PHP],
    flag: 'us',
    countryName: 'UNITED STATES',
    feePercentage: 5,
    insertHeading: 'Please Insert US Dollar Bill',
    insertNote: 'Ensure your bill is in correct orientation and in good condition. Refer to the figure below.',
    acceptedDenomNote: '($10, $50, $100 only)',
  },
  [FOREX_SERVICE_TYPES.PHP_TO_USD]: {
    name: 'PHP-to-USD',
    displayName: 'PHP to USD',
    fromCurrency: CURRENCIES.PHP,
    toCurrency: CURRENCIES.USD,
    fromSymbol: CURRENCY_SYMBOLS.PHP,
    toSymbol: CURRENCY_SYMBOLS.USD,
    acceptDenominations: FOREX_DENOMINATIONS.PHP,
    dispenseDenominations: FOREX_DENOMINATIONS.USD,
    amountOptions: FOREX_AMOUNT_OPTIONS[FOREX_SERVICE_TYPES.PHP_TO_USD],
    flag: 'ph',
    countryName: 'PHILIPPINES',
    feePercentage: 5,
    insertHeading: 'Please Insert Money',
    insertNote: 'Ensure your bill is in correct orientation and in good condition. Refer to the figure below.',
    acceptedDenomNote: '',
    selectLabel: 'Select Dollar to Dispense',
  },
  [FOREX_SERVICE_TYPES.EUR_TO_PHP]: {
    name: 'EUR-to-PHP',
    displayName: 'EUR to PHP',
    fromCurrency: CURRENCIES.EUR,
    toCurrency: CURRENCIES.PHP,
    fromSymbol: CURRENCY_SYMBOLS.EUR,
    toSymbol: CURRENCY_SYMBOLS.PHP,
    acceptDenominations: FOREX_DENOMINATIONS.EUR,
    dispenseDenominations: FOREX_DENOMINATIONS.PHP,
    amountOptions: FOREX_AMOUNT_OPTIONS[FOREX_SERVICE_TYPES.EUR_TO_PHP],
    flag: 'eu',
    countryName: 'EUROPE',
    feePercentage: 5,
    insertHeading: 'Please Insert Euro Bill',
    insertNote: 'Ensure your bill is in correct orientation and in good condition. Refer to the figure below.',
    acceptedDenomNote: '(€5, €10, €20 only)',
  },
  [FOREX_SERVICE_TYPES.PHP_TO_EUR]: {
    name: 'PHP-to-EUR',
    displayName: 'PHP to EUR',
    fromCurrency: CURRENCIES.PHP,
    toCurrency: CURRENCIES.EUR,
    fromSymbol: CURRENCY_SYMBOLS.PHP,
    toSymbol: CURRENCY_SYMBOLS.EUR,
    acceptDenominations: FOREX_DENOMINATIONS.PHP,
    dispenseDenominations: FOREX_DENOMINATIONS.EUR,
    amountOptions: FOREX_AMOUNT_OPTIONS[FOREX_SERVICE_TYPES.PHP_TO_EUR],
    flag: 'ph',
    countryName: 'PHILIPPINES',
    feePercentage: 5,
    insertHeading: 'Please Insert Money',
    insertNote: 'Ensure your bill is in correct orientation and in good condition. Refer to the figure below.',
    acceptedDenomNote: '',
    selectLabel: 'Select Euro to Dispense',
  },
};

// Forex services list for service selection screen
export const FOREX_SERVICES = [
  {
    type: FOREX_SERVICE_TYPES.USD_TO_PHP,
    title: 'USD-to-PHP',
    icon: 'usd-to-php',
    fromFlag: 'us',
    toFlag: 'ph',
  },
  {
    type: FOREX_SERVICE_TYPES.PHP_TO_USD,
    title: 'PHP-to-USD',
    icon: 'php-to-usd',
    fromFlag: 'ph',
    toFlag: 'us',
  },
  {
    type: FOREX_SERVICE_TYPES.EUR_TO_PHP,
    title: 'EUR-to-PHP',
    icon: 'eur-to-php',
    fromFlag: 'eu',
    toFlag: 'ph',
  },
  {
    type: FOREX_SERVICE_TYPES.PHP_TO_EUR,
    title: 'PHP-to-EUR',
    icon: 'php-to-eur',
    fromFlag: 'ph',
    toFlag: 'eu',
  },
];

// Timer durations for forex
export const FOREX_TIMER_DURATIONS = {
  INSERT_MONEY: 60,      // 60 seconds to insert money
  RATE_REFRESH: 60,      // Rate "changes" every 60 seconds
  AUTO_ADVANCE: 2500,    // 2.5 seconds on processing screen
};

// Mock data for demo/navigation
export const FOREX_MOCK_DATA = {
  [FOREX_SERVICE_TYPES.USD_TO_PHP]: {
    rate: 58.7656,
    selectedAmount: 5,
    convertedAmount: 293,
    feePercentage: 5,
    feeAmount: 30,
    amountToDispense: 263,
  },
  [FOREX_SERVICE_TYPES.PHP_TO_USD]: {
    rate: 0.0170,
    selectedAmount: 5,
    convertedAmount: 294,
    feePercentage: 5,
    feeAmount: 30,
    totalDue: 324,
    amountToDispense: 5,
  },
  [FOREX_SERVICE_TYPES.EUR_TO_PHP]: {
    rate: 61.7246,
    selectedAmount: 5,
    convertedAmount: 308,
    feePercentage: 5,
    feeAmount: 15,
    amountToDispense: 293,
  },
  [FOREX_SERVICE_TYPES.PHP_TO_EUR]: {
    rate: 0.0162,
    selectedAmount: 5,
    convertedAmount: 308,
    feePercentage: 5,
    feeAmount: 15,
    totalDue: 323,
    amountToDispense: 5,
  },
};

// Helper functions

/**
 * Format currency amount with symbol
 * @param {number} amount - The amount to format
 * @param {string} currency - Currency code (PHP, USD, EUR)
 * @returns {string} Formatted amount with symbol
 */
export const formatCurrency = (amount, currency) => {
  const symbol = CURRENCY_SYMBOLS[currency] || '';
  if (currency === CURRENCIES.PHP) {
    return `P${amount.toLocaleString()}`;
  }
  return `${symbol}${amount.toLocaleString()}`;
};

/**
 * Get exchange rate for a currency pair
 * @param {string} fromCurrency - Source currency
 * @param {string} toCurrency - Target currency
 * @returns {number} Exchange rate
 */
export const getExchangeRate = (fromCurrency, toCurrency) => {
  if (fromCurrency === CURRENCIES.PHP) {
    // PHP to foreign: use inverse rate
    return 1 / MOCK_EXCHANGE_RATES[toCurrency];
  }
  // Foreign to PHP
  return MOCK_EXCHANGE_RATES[fromCurrency];
};

/**
 * Calculate conversion with fee
 * @param {number} amount - Amount in source currency
 * @param {string} fromCurrency - Source currency
 * @param {string} toCurrency - Target currency
 * @param {number} feePercentage - Fee percentage
 * @returns {Object} Conversion details
 */
export const calculateConversion = (amount, fromCurrency, toCurrency, feePercentage = 5) => {
  const rate = getExchangeRate(fromCurrency, toCurrency);
  const convertedAmount = amount * rate;
  const feeAmount = Math.round(convertedAmount * (feePercentage / 100));
  const amountToDispense = Math.round(convertedAmount - feeAmount);

  return {
    rate,
    convertedAmount: Math.round(convertedAmount),
    feePercentage,
    feeAmount,
    amountToDispense,
  };
};

/**
 * Check if service type converts FROM foreign currency TO PHP
 * @param {string} serviceType - Forex service type
 * @returns {boolean}
 */
export const isForeignToPhp = (serviceType) => {
  return serviceType === FOREX_SERVICE_TYPES.USD_TO_PHP ||
         serviceType === FOREX_SERVICE_TYPES.EUR_TO_PHP;
};

/**
 * Check if service type converts FROM PHP TO foreign currency
 * @param {string} serviceType - Forex service type
 * @returns {boolean}
 */
export const isPhpToForeign = (serviceType) => {
  return serviceType === FOREX_SERVICE_TYPES.PHP_TO_USD ||
         serviceType === FOREX_SERVICE_TYPES.PHP_TO_EUR;
};

/**
 * Get the forex config for a service type
 * @param {string} serviceType - Forex service type
 * @returns {Object} Service configuration
 */
export const getForexConfig = (serviceType) => {
  return FOREX_CONFIG[serviceType] || null;
};
