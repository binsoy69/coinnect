import { SERVICE_TYPES } from "./routes";

// Service configuration for each conversion type
export const SERVICE_CONFIG = {
  [SERVICE_TYPES.BILL_TO_BILL]: {
    name: "Bill-to-Bill",
    displayName: "Bill-to-Bill Conversion",
    shortName: "Bill to Bill",
    amountOptions: [20, 50, 100, 200, 500, 1000],
    dispenseOptions: [20, 50, 100, 200, 500],
    insertType: "bill",
    dispenseType: "bill",
    fee: 10,
    insertCounters: [20, 50, 100, 200],
    insertNote:
      "Ensure your bill is in correct orientation and in good condition. Refer to the figure below.",
    insertHeading: "Please Insert Bill",
    icon: "/assets/Black_coin to bill.png",
  },
  [SERVICE_TYPES.BILL_TO_COIN]: {
    name: "Bill-to-Coin",
    displayName: "Bill-to-Coin Conversion",
    shortName: "Bill to Coin",
    amountOptions: [20, 50, 100, 200],
    dispenseOptions: [1, 5, 10, 20],
    insertType: "bill",
    dispenseType: "coin",
    fee: 15,
    insertCounters: [20, 50, 100, 200],
    insertNote:
      "Ensure your bill is in correct orientation and in good condition.",
    insertHeading: "Please Insert Bill",
    icon: "/assets/Black_coin to bill.png",
  },
  [SERVICE_TYPES.COIN_TO_BILL]: {
    name: "Coin-to-Bill",
    displayName: "Coin-to-Bill Conversion",
    shortName: "Coin to Bill",
    amountOptions: [20, 50, 100, 200],
    dispenseOptions: [20, 50, 100, 200],
    insertType: "coin",
    dispenseType: "bill",
    fee: 3,
    insertCounters: [1, 5, 10, 20],
    insertNote:
      "Excess coins will be dispensed. Tap proceed and wait for confirmation.",
    insertHeading: "Please Insert Coins",
    icon: "/assets/Black_coin to bill.png",
  },
};

// Transaction types for the main selection screen
export const TRANSACTION_TYPES = [
  {
    id: "forex",
    name: "Foreign Exchange",
    description: "Currency conversion",
    icon: "/assets/forex.png",
    color: "coinnect-forex",
    bgClass: "bg-coinnect-forex",
    enabled: true,
  },
  {
    id: "converter",
    name: "Coin and Bill Converter",
    description: "Convert bills and coins",
    icon: "/assets/money-converter.png",
    color: "coinnect-converter",
    bgClass: "bg-coinnect-primary",
    enabled: true,
  },
  {
    id: "ewallet",
    name: "E-Wallet",
    description: "Cash in / Cash out",
    icon: "/assets/ewallet.png",
    color: "coinnect-ewallet",
    bgClass: "bg-coinnect-ewallet",
    enabled: true,
  },
];

// Service cards for money converter selection
export const CONVERTER_SERVICES = [
  {
    type: SERVICE_TYPES.COIN_TO_BILL,
    name: "Coin-to-Bill",
    icon: "/assets/2coin to bill.png",
  },
  {
    type: SERVICE_TYPES.BILL_TO_COIN,
    name: "Bill-to-Coin",
    icon: "/assets/1bill to coinn.png",
  },
  {
    type: SERVICE_TYPES.BILL_TO_BILL,
    name: "Bill-to-Bill",
    icon: "/assets/3bill to bill.png",
  },
];

// Default transaction state
export const DEFAULT_TRANSACTION_STATE = {
  serviceType: null,
  selectedAmount: null,
  includeFee: true,
  fee: 0,
  totalDue: 0,
  selectedDispenseDenominations: [],
  insertedCounts: {},
  moneyInserted: 0,
};

// Timer durations (in seconds)
export const TIMER_DURATIONS = {
  INSERT_MONEY: 60,
  SESSION_TIMEOUT: 120,
  WARNING_COUNTDOWN: 15,
};

// Main transaction type label
export const TRANSACTION_TYPE_LABEL = "Coin and Bill Converter";
