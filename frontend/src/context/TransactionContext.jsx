/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { SERVICE_CONFIG, DEFAULT_TRANSACTION_STATE } from '../constants/mockData';
import { SERVICE_TYPES } from '../constants/routes';
import { API_BASE } from '../constants/api';

const TransactionContext = createContext(null);

export function TransactionProvider({ children }) {
  const [transaction, setTransaction] = useState(DEFAULT_TRANSACTION_STATE);
  const [backendTransactionId, setBackendTransactionId] = useState(null);
  const [backendState, setBackendState] = useState(null);
  const [dispenseProgress, setDispenseProgress] = useState(null);
  const [machineFees, setMachineFees] = useState(null);

  // Fetch machine fee configuration from backend
  useEffect(() => {
    fetch(`${API_BASE}/admin/fees`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setMachineFees(data);
      })
      .catch(() => {});
  }, []);

  // Helper to get fee for a service type
  const getFeeForService = useCallback(
    (serviceType) => {
      if (machineFees) {
        if (serviceType === SERVICE_TYPES.BILL_TO_BILL) return machineFees.fee_bill_to_bill ?? 10;
        if (serviceType === SERVICE_TYPES.BILL_TO_COIN) return machineFees.fee_bill_to_coin ?? 15;
        if (serviceType === SERVICE_TYPES.COIN_TO_BILL) return machineFees.fee_coin_to_bill ?? 3;
      }
      return SERVICE_CONFIG[serviceType]?.fee || 0;
    },
    [machineFees]
  );

  // Initialize transaction with service type
  const startTransaction = useCallback((serviceType) => {
    const config = SERVICE_CONFIG[serviceType];
    if (!config) return;
    const fee = getFeeForService(serviceType);

    setTransaction({
      ...DEFAULT_TRANSACTION_STATE,
      serviceType,
      fee,
    });
    setBackendTransactionId(null);
    setBackendState(null);
    setDispenseProgress(null);
  }, [getFeeForService]);

  // Set selected amount
  const setSelectedAmount = useCallback((amount) => {
    setTransaction(prev => {
      const feeVal = getFeeForService(prev.serviceType);
      const userAddsFee = prev.serviceType === SERVICE_TYPES.COIN_TO_BILL;
      return {
        ...prev,
        selectedAmount: amount,
        fee: feeVal,
        totalDue: amount + (userAddsFee ? feeVal : 0),
      };
    });
  }, [getFeeForService]);

  const applyAuthoritativeTerms = useCallback((state) => {
    setTransaction(prev => ({
      ...prev,
      fee: state.fee,
      totalDue: state.total_due,
      payoutAmount: state.payout_amount,
    }));
  }, []);

  // Set selected dispense denominations
  const setSelectedDispenseDenominations = useCallback((denominations) => {
    setTransaction(prev => ({
      ...prev,
      selectedDispenseDenominations: denominations,
    }));
  }, []);

  // Set selected dispense counts dictionary (e.g. { 500: 1, 100: 4, 50: 2 })
  const setSelectedDispenseCounts = useCallback((counts) => {
    setTransaction(prev => {
      const denoms = Object.entries(counts)
        .filter(([, count]) => count > 0)
        .map(([denom]) => Number(denom));
      return {
        ...prev,
        selectedDispenseCounts: counts,
        selectedDispenseDenominations: denoms,
      };
    });
  }, []);

  // Set count for a single dispense denomination
  const setDispenseCount = useCallback((denom, count) => {
    setTransaction(prev => {
      const newCounts = { ...prev.selectedDispenseCounts, [denom]: Math.max(0, count) };
      const denoms = Object.entries(newCounts)
        .filter(([, c]) => c > 0)
        .map(([d]) => Number(d));
      return {
        ...prev,
        selectedDispenseCounts: newCounts,
        selectedDispenseDenominations: denoms,
      };
    });
  }, []);

  // Toggle a dispense denomination
  const toggleDispenseDenomination = useCallback((denom) => {
    setTransaction(prev => {
      const current = prev.selectedDispenseDenominations;
      const isSelected = current.includes(denom);
      const newDenoms = isSelected
        ? current.filter(d => d !== denom)
        : [...current, denom];
      const newCounts = { ...prev.selectedDispenseCounts };
      if (isSelected) {
        delete newCounts[denom];
      } else {
        newCounts[denom] = 1;
      }
      return {
        ...prev,
        selectedDispenseDenominations: newDenoms,
        selectedDispenseCounts: newCounts,
      };
    });
  }, []);

  // Update inserted money counts
  const updateInsertedCount = useCallback((denom, count) => {
    setTransaction(prev => {
      const newCounts = { ...prev.insertedCounts, [denom]: count };
      const moneyInserted = Object.entries(newCounts).reduce(
        (sum, [d, c]) => sum + (parseInt(d) * c),
        0
      );
      return {
        ...prev,
        insertedCounts: newCounts,
        moneyInserted,
      };
    });
  }, []);

  // Add inserted money (simulates hardware input)
  const addInsertedMoney = useCallback((denom, count = 1) => {
    setTransaction(prev => {
      const numericDenom = typeof denom === 'number' ? denom : (parseInt(String(denom).replace(/\D/g, ''), 10) || 0);
      const currentCount = prev.insertedCounts[numericDenom] || 0;
      const newCounts = { ...prev.insertedCounts, [numericDenom]: currentCount + count };
      const moneyInserted = Object.entries(newCounts).reduce(
        (sum, [d, c]) => sum + ((parseInt(d, 10) || 0) * c),
        0
      );
      return {
        ...prev,
        insertedCounts: newCounts,
        moneyInserted,
      };
    });
  }, []);

  // Reset transaction to initial state
  const resetTransaction = useCallback(() => {
    setTransaction(DEFAULT_TRANSACTION_STATE);
    setBackendTransactionId(null);
    setBackendState(null);
    setDispenseProgress(null);
  }, []);

  // Get current service config
  const getServiceConfig = useCallback(() => {
    return SERVICE_CONFIG[transaction.serviceType] || null;
  }, [transaction.serviceType]);

  // Check if amount matches total due
  const isAmountMatched = useCallback(() => {
    return transaction.totalDue > 0 && transaction.moneyInserted >= transaction.totalDue;
  }, [transaction.moneyInserted, transaction.totalDue]);

  // Calculate money to dispense
  const getMoneyToDispense = useCallback(() => {
    if (transaction.serviceType === SERVICE_TYPES.COIN_TO_BILL) {
      const payout = transaction.payoutAmount ?? transaction.selectedAmount ?? 0;
      const excessRefund = Math.max(
        0,
        transaction.moneyInserted - transaction.totalDue,
      );
      return payout + excessRefund;
    }
    if (transaction.payoutAmount != null) return transaction.payoutAmount;
    return Math.max(0, (transaction.selectedAmount || 0) - (transaction.fee || 0));
  }, [
    transaction.fee,
    transaction.moneyInserted,
    transaction.payoutAmount,
    transaction.selectedAmount,
    transaction.serviceType,
    transaction.totalDue,
  ]);

  const value = {
    transaction,
    backendTransactionId,
    setBackendTransactionId,
    backendState,
    setBackendState,
    dispenseProgress,
    setDispenseProgress,
    startTransaction,
    setSelectedAmount,
    applyAuthoritativeTerms,
    setSelectedDispenseDenominations,
    setSelectedDispenseCounts,
    setDispenseCount,
    toggleDispenseDenomination,
    updateInsertedCount,
    addInsertedMoney,
    resetTransaction,
    getServiceConfig,
    isAmountMatched,
    getMoneyToDispense,
  };

  return (
    <TransactionContext.Provider value={value}>
      {children}
    </TransactionContext.Provider>
  );
}

export function useTransaction() {
  const context = useContext(TransactionContext);
  if (!context) {
    throw new Error('useTransaction must be used within a TransactionProvider');
  }
  return context;
}

export default TransactionContext;
