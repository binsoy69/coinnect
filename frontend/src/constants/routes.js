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

  // E-Wallet routes
  EWALLET: '/ewallet',
  EWALLET_SERVICE: '/ewallet/:provider/service',
  EWALLET_REMINDER: '/ewallet/reminder',

  // E-Wallet dynamic routes - :type = 'gcash-cash-in' | 'gcash-cash-out' | 'maya-cash-in' | 'maya-cash-out'
  EWALLET_FEE: '/ewallet/:type/fee',
  EWALLET_MOBILE: '/ewallet/:type/mobile',
  EWALLET_AMOUNT: '/ewallet/:type/amount',
  EWALLET_CONFIRM: '/ewallet/:type/confirm',
  EWALLET_INSERT_BILLS: '/ewallet/:type/insert-bills',
  EWALLET_INSERT_COINS: '/ewallet/:type/insert-coins',
  EWALLET_DETAILS: '/ewallet/:type/details',
  EWALLET_QR: '/ewallet/:type/qr',
  EWALLET_VERIFY: '/ewallet/:type/verify',
  EWALLET_PROCESSING: '/ewallet/:type/processing',
  EWALLET_SUMMARY: '/ewallet/:type/summary',
  EWALLET_SUCCESS: '/ewallet/:type/success',
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

// E-Wallet service type constants
export const EWALLET_SERVICE_TYPES = {
  GCASH_CASH_IN: 'gcash-cash-in',
  GCASH_CASH_OUT: 'gcash-cash-out',
  MAYA_CASH_IN: 'maya-cash-in',
  MAYA_CASH_OUT: 'maya-cash-out',
};

// E-Wallet provider constants
export const EWALLET_PROVIDERS = {
  GCASH: 'gcash',
  MAYA: 'maya',
};

// Helper to generate e-wallet route with type parameter
export const getEWalletRoute = (baseRoute, ewalletType) => {
  return baseRoute.replace(':type', ewalletType);
};

// Helper to generate e-wallet route with provider parameter
export const getEWalletProviderRoute = (baseRoute, provider) => {
  return baseRoute.replace(':provider', provider);
};
