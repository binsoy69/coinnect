import { EWALLET_SERVICE_TYPES, EWALLET_PROVIDERS } from "./routes";
export { EWALLET_SERVICE_TYPES, EWALLET_PROVIDERS };

// Provider configurations
export const EWALLET_PROVIDERS_CONFIG = {
  [EWALLET_PROVIDERS.GCASH]: {
    name: "GCash",
    icon: "/assets/GCASH CASH IN w.png",
    color: "bg-coinnect-gcash",
    textColor: "text-coinnect-gcash",
  },
  [EWALLET_PROVIDERS.MAYA]: {
    name: "Maya",
    icon: "/assets/MAYA CASH IN w.png",
    color: "bg-coinnect-maya",
    textColor: "text-coinnect-maya",
  },
};

// Provider list for selection screen
export const EWALLET_PROVIDER_LIST = [
  {
    id: EWALLET_PROVIDERS.GCASH,
    name: "GCash",
    icon: "/assets/GCASH w.png",
  },
  {
    id: EWALLET_PROVIDERS.MAYA,
    name: "Maya",
    icon: "/assets/MAYA w.png",
  },
];

// Service list per provider (for service selection screen)
export const EWALLET_SERVICES = {
  [EWALLET_PROVIDERS.GCASH]: [
    {
      type: EWALLET_SERVICE_TYPES.GCASH_CASH_IN,
      name: "Cash In",
      icon: "/assets/GCASH CASH IN w.png",
    },
    {
      type: EWALLET_SERVICE_TYPES.GCASH_CASH_OUT,
      name: "Cash Out",
      icon: "/assets/GCASH CASH OUT w.png",
    },
  ],
  [EWALLET_PROVIDERS.MAYA]: [
    {
      type: EWALLET_SERVICE_TYPES.MAYA_CASH_IN,
      name: "Cash In",
      icon: "/assets/MAYA CASH IN w.png",
    },
    {
      type: EWALLET_SERVICE_TYPES.MAYA_CASH_OUT,
      name: "Cash Out",
      icon: "/assets/MAYA CASH OUT w.png",
    },
  ],
};

// Bill denominations for insert bills screen
export const EWALLET_BILL_DENOMINATIONS = [20, 50, 100, 200, 500, 1000];

// Coin denominations for insert coins screen
export const EWALLET_COIN_DENOMINATIONS = [1, 5, 10, 20];

// All denominations shown on insert bills screen counters
export const EWALLET_ALL_DENOMINATIONS = [
  1, 5, 10, 20, 50, 100, 200, 500, 1000,
];

// Service configuration for each e-wallet type
export const EWALLET_CONFIG = {
  [EWALLET_SERVICE_TYPES.GCASH_CASH_IN]: {
    name: "GCash Cash In",
    displayName: "GCash Cash In",
    provider: EWALLET_PROVIDERS.GCASH,
    providerName: "GCash",
    direction: "cash-in",
    icon: "/assets/GCASH CASH IN w.png",
    iconWhite: "/assets/GCASH CASH IN w.png",
  },
  [EWALLET_SERVICE_TYPES.GCASH_CASH_OUT]: {
    name: "GCash Cash Out",
    displayName: "GCash Cash Out",
    provider: EWALLET_PROVIDERS.GCASH,
    providerName: "GCash",
    direction: "cash-out",
    icon: "/assets/GCASH CASH OUT w.png",
    iconWhite: "/assets/GCASH CASH OUT w.png",
  },
  [EWALLET_SERVICE_TYPES.MAYA_CASH_IN]: {
    name: "Maya Cash In",
    displayName: "Maya Cash In",
    provider: EWALLET_PROVIDERS.MAYA,
    providerName: "Maya",
    direction: "cash-in",
    icon: "/assets/MAYA CASH IN w.png",
    iconWhite: "/assets/MAYA CASH IN w.png",
  },
  [EWALLET_SERVICE_TYPES.MAYA_CASH_OUT]: {
    name: "Maya Cash Out",
    displayName: "Maya Cash Out",
    provider: EWALLET_PROVIDERS.MAYA,
    providerName: "Maya",
    direction: "cash-out",
    icon: "/assets/MAYA CASH OUT w.png",
    iconWhite: "/assets/MAYA CASH OUT w.png",
  },
};

// Timer durations
export const EWALLET_TIMER_DURATIONS = {
  INSERT_MONEY: 60,
  AUTO_ADVANCE: 2500,
};

// Calculate fee based on amount
export const calculateFee = (amount, feeTiers) => {
  for (const tier of feeTiers) {
    if (amount >= tier.min && (tier.max == null || amount <= tier.max)) {
      return tier.fee;
    }
  }
  return 0;
};

// Check if service type is cash-in
export const isCashIn = (serviceType) => {
  return serviceType?.endsWith("cash-in") || false;
};

// Check if service type is cash-out
export const isCashOut = (serviceType) => {
  return serviceType?.endsWith("cash-out") || false;
};

// Get provider from service type
export const getProviderFromType = (serviceType) => {
  if (serviceType?.startsWith("gcash")) return EWALLET_PROVIDERS.GCASH;
  if (serviceType?.startsWith("maya")) return EWALLET_PROVIDERS.MAYA;
  return null;
};

// Get e-wallet config for a service type
export const getEWalletConfig = (serviceType) => {
  return EWALLET_CONFIG[serviceType] || null;
};
