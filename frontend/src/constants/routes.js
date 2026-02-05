// Route path constants
export const ROUTES = {
  HOME: '/',
  SELECT_TRANSACTION: '/select-transaction',
  MONEY_CONVERTER: '/money-converter',
  REMINDER: '/money-converter/reminder',

  // Dynamic routes - :type = 'bill-to-bill' | 'bill-to-coin' | 'coin-to-bill'
  SELECT_AMOUNT: '/money-converter/:type/amount',
  SELECT_DISPENSE: '/money-converter/:type/dispense',
  TRANSACTION_FEE: '/money-converter/:type/fee',
  CONFIRMATION: '/money-converter/:type/confirm',
  INSERT_MONEY: '/money-converter/:type/insert',
  TRANSACTION_SUMMARY: '/money-converter/:type/summary',
  PROCESSING: '/money-converter/:type/processing',
  SUCCESS: '/money-converter/:type/success',
  WARNING: '/money-converter/:type/warning',

  // Forex routes
  FOREX: '/forex',
  FOREX_REMINDER: '/forex/reminder',

  // Forex dynamic routes - :type = 'usd-to-php' | 'php-to-usd' | 'eur-to-php' | 'php-to-eur'
  FOREX_RATE: '/forex/:type/rate',
  FOREX_CONFIRM: '/forex/:type/confirm',
  FOREX_INSERT: '/forex/:type/insert',
  FOREX_CONVERSION: '/forex/:type/conversion',
  FOREX_SUMMARY: '/forex/:type/summary',
  FOREX_PROCESSING: '/forex/:type/processing',
  FOREX_SUCCESS: '/forex/:type/success',
  FOREX_WARNING: '/forex/:type/warning',
};

// Service type constants
export const SERVICE_TYPES = {
  BILL_TO_BILL: 'bill-to-bill',
  BILL_TO_COIN: 'bill-to-coin',
  COIN_TO_BILL: 'coin-to-bill',
};

// Forex service type constants
export const FOREX_SERVICE_TYPES = {
  USD_TO_PHP: 'usd-to-php',
  PHP_TO_USD: 'php-to-usd',
  EUR_TO_PHP: 'eur-to-php',
  PHP_TO_EUR: 'php-to-eur',
};

// Helper to generate route with type parameter
export const getServiceRoute = (baseRoute, serviceType) => {
  return baseRoute.replace(':type', serviceType);
};

// Helper to generate forex route with type parameter
export const getForexRoute = (baseRoute, forexType) => {
  return baseRoute.replace(':type', forexType);
};
