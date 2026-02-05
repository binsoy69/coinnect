// PHP Bill Denominations
export const PHP_BILL_DENOMINATIONS = [20, 50, 100, 200, 500, 1000];

// PHP Coin Denominations
export const PHP_COIN_DENOMINATIONS = [1, 5, 10, 20];

// Display format for denominations
export const DENOMINATION_DISPLAY = {
  1: 'P1',
  5: 'P5',
  10: 'P10',
  20: 'P20',
  50: 'P50',
  100: 'P100',
  200: 'P200',
  500: 'P500',
  1000: 'P1000',
};

// Format amount with peso sign
export const formatPeso = (amount) => {
  return `P${amount.toLocaleString()}`;
};

// Format denomination count
export const formatDenomCount = (denom, count) => {
  return `${DENOMINATION_DISPLAY[denom]} = ${count}x`;
};
