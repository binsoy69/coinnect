/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback } from "react";
import {
  EWALLET_CONFIG,
  EWALLET_PROVIDERS_CONFIG,
  calculateFee,
  isCashIn,
} from "../constants/ewalletData";
import { API_BASE, ENABLE_KEYBOARD_SIM } from "../constants/api";

// Default state for e-wallet transaction
const DEFAULT_EWALLET_STATE = {
  provider: null, // 'gcash' | 'maya'
  serviceType: null, // 'gcash-cash-in' | 'gcash-cash-out' | 'maya-cash-in' | 'maya-cash-out'
  mobileNumber: "",
  accountName: "",
  amount: 0, // Total due (amount to transfer + fee)
  fee: 0, // Calculated transaction fee
  transferAmount: 0, // Amount that goes to e-wallet (cash-in) or dispensed (cash-out)
  totalDue: 0, // Total amount user needs to insert
  insertedBillCounts: {}, // { denomination: count } for bills
  insertedCoinCounts: {}, // { denomination: count } for coins
  totalBillsInserted: 0,
  totalCoinsInserted: 0,
  totalInserted: 0, // bills + coins total value
  transactionId: null,
  backendState: null,
  gatewayError: null,
  feeTiers: [],
};

const EWalletContext = createContext(null);

export function EWalletProvider({ children }) {
  const [ewallet, setEWallet] = useState(DEFAULT_EWALLET_STATE);

  // Start e-wallet transaction by selecting provider
  const startEWalletTransaction = useCallback((provider) => {
    setEWallet({
      ...DEFAULT_EWALLET_STATE,
      provider,
    });
  }, []);

  // Set the service type (e.g., 'gcash-cash-in')
  const setServiceType = useCallback((serviceType) => {
    const config = EWALLET_CONFIG[serviceType];
    if (!config) return;

    setEWallet((prev) => ({
      ...prev,
      serviceType,
    }));
  }, []);

  // Set mobile number
  const setMobileNumber = useCallback((mobileNumber) => {
    setEWallet((prev) => ({
      ...prev,
      mobileNumber,
    }));
  }, []);

  const setAccountName = useCallback((accountName) => {
    setEWallet((prev) => ({ ...prev, accountName }));
  }, []);

  // Set amount and calculate fee/totalDue
  const setAmount = useCallback((amount) => {
    setEWallet((prev) => {
      const fee = calculateFee(amount, prev.feeTiers);

      if (isCashIn(prev.serviceType)) {
        // Cash In: user inserts totalDue, fee is deducted, rest goes to e-wallet
        // totalDue = amount (what user typed), transferAmount = amount - fee
        return {
          ...prev,
          amount,
          fee,
          transferAmount: amount - fee,
          totalDue: amount,
        };
      } else {
        // Cash Out: user wants to receive transferAmount in cash
        // totalDue = transferAmount + fee (paid via app)
        return {
          ...prev,
          amount,
          fee,
          transferAmount: amount - fee,
          totalDue: amount,
        };
      }
    });
  }, []);

  // Add inserted bill
  const addInsertedBill = useCallback((denom, count = 1) => {
    setEWallet((prev) => {
      const currentCount = prev.insertedBillCounts[denom] || 0;
      const newBillCounts = {
        ...prev.insertedBillCounts,
        [denom]: currentCount + count,
      };
      const totalBillsInserted = Object.entries(newBillCounts).reduce(
        (sum, [d, c]) => sum + parseInt(d) * c,
        0,
      );
      const totalInserted = totalBillsInserted + prev.totalCoinsInserted;
      return {
        ...prev,
        insertedBillCounts: newBillCounts,
        totalBillsInserted,
        totalInserted,
      };
    });
  }, []);

  // Add inserted coin
  const addInsertedCoin = useCallback((denom, count = 1) => {
    setEWallet((prev) => {
      const currentCount = prev.insertedCoinCounts[denom] || 0;
      const newCoinCounts = {
        ...prev.insertedCoinCounts,
        [denom]: currentCount + count,
      };
      const totalCoinsInserted = Object.entries(newCoinCounts).reduce(
        (sum, [d, c]) => sum + parseInt(d) * c,
        0,
      );
      const totalInserted = prev.totalBillsInserted + totalCoinsInserted;
      return {
        ...prev,
        insertedCoinCounts: newCoinCounts,
        totalCoinsInserted,
        totalInserted,
      };
    });
  }, []);

  const request = useCallback(async (path, options = {}) => {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...options.headers },
      ...options,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || `Request failed (${response.status})`);
    }
    return data;
  }, []);

  const syncBackendState = useCallback((data) => {
    setEWallet((prev) => ({
      ...prev,
      transactionId: data.transaction_id,
      backendState: data,
      gatewayError: data.error_message || null,
      totalInserted: data.inserted_amount ?? prev.totalInserted,
      insertedBillCounts:
        data.inserted_denominations || prev.insertedBillCounts,
      amount: data.amount ?? prev.amount,
      fee: data.fee ?? prev.fee,
      transferAmount: data.transfer_amount ?? prev.transferAmount,
      totalDue: data.total_due ?? prev.totalDue,
    }));
    return data;
  }, []);

  const loadFeeTiers = useCallback(async () => {
    const data = await request("/ewallet/config");
    setEWallet((prev) => ({
      ...prev,
      feeTiers: data.fee_tiers || [],
    }));
    return data.fee_tiers || [];
  }, [request]);

  const startBackendTransaction = useCallback(async () => {
    try {
      const cashIn = isCashIn(ewallet.serviceType);
      const payload = {
        provider: ewallet.provider,
        direction: cashIn ? "cash-in" : "cash-out",
        amount: ewallet.totalDue,
      };
      if (cashIn) {
        payload.mobile_number = ewallet.mobileNumber;
        payload.account_name = ewallet.accountName;
      }
      const data = await request("/ewallet/transactions", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      return syncBackendState(data);
    } catch (error) {
      setEWallet((prev) => ({ ...prev, gatewayError: error.message }));
      throw error;
    }
  }, [ewallet, request, syncBackendState]);

  const refreshBackendTransaction = useCallback(async () => {
    if (!ewallet.transactionId) return null;
    const data = await request(
      `/ewallet/transactions/${ewallet.transactionId}`,
    );
    return syncBackendState(data);
  }, [ewallet.transactionId, request, syncBackendState]);

  const simulateCashInsert = useCallback(
    async (denomination) => {
      if (!ewallet.transactionId || !ENABLE_KEYBOARD_SIM) return null;
      const data = await request(
        `/ewallet/transactions/${ewallet.transactionId}/simulate-insert`,
        {
          method: "POST",
          body: JSON.stringify({ denomination }),
        },
      );
      return syncBackendState(data);
    },
    [ewallet.transactionId, request, syncBackendState],
  );

  const acceptPhysicalBill = useCallback(async () => {
    if (!ewallet.transactionId) return null;
    const data = await request(
      `/ewallet/transactions/${ewallet.transactionId}/accept-bill`,
      { method: "POST" },
    );
    return syncBackendState(data);
  }, [ewallet.transactionId, request, syncBackendState]);

  const confirmBackendTransaction = useCallback(async () => {
    if (!ewallet.transactionId) return null;
    const data = await request(
      `/ewallet/transactions/${ewallet.transactionId}/confirm`,
      { method: "POST" },
    );
    return syncBackendState(data);
  }, [ewallet.transactionId, request, syncBackendState]);

  // Reset transaction
  const resetTransaction = useCallback(() => {
    setEWallet(DEFAULT_EWALLET_STATE);
  }, []);

  // Check if inserted amount matches total due
  const isAmountMatched = useCallback(() => {
    return ewallet.totalInserted >= ewallet.totalDue && ewallet.totalDue > 0;
  }, [ewallet.totalInserted, ewallet.totalDue]);

  // Get remaining amount needed
  const getRemainingAmount = useCallback(() => {
    return Math.max(0, ewallet.totalDue - ewallet.totalInserted);
  }, [ewallet.totalDue, ewallet.totalInserted]);

  // Get current e-wallet config
  const getEWalletConfig = useCallback(() => {
    return EWALLET_CONFIG[ewallet.serviceType] || null;
  }, [ewallet.serviceType]);

  // Get provider-specific styles
  const getProviderStyles = useCallback(() => {
    const config = EWALLET_PROVIDERS_CONFIG[ewallet.provider];
    if (!config) {
      return {
        bg: "bg-coinnect-ewallet",
        text: "text-coinnect-ewallet",
        buttonVariant: "ewallet",
      };
    }
    return {
      bg: config.color,
      text: config.textColor,
      buttonVariant: ewallet.provider, // 'gcash' or 'maya'
    };
  }, [ewallet.provider]);

  const value = {
    ewallet,
    startEWalletTransaction,
    setServiceType,
    setMobileNumber,
    setAccountName,
    setAmount,
    addInsertedBill,
    addInsertedCoin,
    startBackendTransaction,
    refreshBackendTransaction,
    simulateCashInsert,
    acceptPhysicalBill,
    syncBackendState,
    confirmBackendTransaction,
    loadFeeTiers,
    resetTransaction,
    isAmountMatched,
    getRemainingAmount,
    getEWalletConfig,
    getProviderStyles,
  };

  return (
    <EWalletContext.Provider value={value}>{children}</EWalletContext.Provider>
  );
}

export function useEWallet() {
  const context = useContext(EWalletContext);
  if (!context) {
    throw new Error("useEWallet must be used within an EWalletProvider");
  }
  return context;
}

export default EWalletContext;
