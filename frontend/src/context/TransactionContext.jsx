/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback } from 'react';
import { SERVICE_CONFIG, DEFAULT_TRANSACTION_STATE } from '../constants/mockData';

const TransactionContext = createContext(null);

export function TransactionProvider({ children }) {
  const [transaction, setTransaction] = useState(DEFAULT_TRANSACTION_STATE);

  // Initialize transaction with service type
  const startTransaction = useCallback((serviceType) => {
    const config = SERVICE_CONFIG[serviceType];
    if (!config) return;

    setTransaction({
      ...DEFAULT_TRANSACTION_STATE,
      serviceType,
      fee: config.fee,
    });
  }, []);

  // Set selected amount
  const setSelectedAmount = useCallback((amount) => {
    setTransaction(prev => {
      const config = SERVICE_CONFIG[prev.serviceType];
      const fee = prev.includeFee ? (config?.fee || 0) : 0;
      return {
        ...prev,
        selectedAmount: amount,
        totalDue: amount + fee,
      };
    });
  }, []);

  // Toggle fee inclusion
  const setIncludeFee = useCallback((include) => {
    setTransaction(prev => {
      const config = SERVICE_CONFIG[prev.serviceType];
      const fee = include ? (config?.fee || 0) : 0;
      return {
        ...prev,
        includeFee: include,
        fee,
        totalDue: (prev.selectedAmount || 0) + fee,
      };
    });
  }, []);

  // Set selected dispense denominations
  const setSelectedDispenseDenominations = useCallback((denominations) => {
    setTransaction(prev => ({
      ...prev,
      selectedDispenseDenominations: denominations,
    }));
  }, []);

  // Toggle a dispense denomination
  const toggleDispenseDenomination = useCallback((denom) => {
    setTransaction(prev => {
      const current = prev.selectedDispenseDenominations;
      const isSelected = current.includes(denom);
      return {
        ...prev,
        selectedDispenseDenominations: isSelected
          ? current.filter(d => d !== denom)
          : [...current, denom],
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
      const currentCount = prev.insertedCounts[denom] || 0;
      const newCounts = { ...prev.insertedCounts, [denom]: currentCount + count };
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

  // Reset transaction to initial state
  const resetTransaction = useCallback(() => {
    setTransaction(DEFAULT_TRANSACTION_STATE);
  }, []);

  // Get current service config
  const getServiceConfig = useCallback(() => {
    return SERVICE_CONFIG[transaction.serviceType] || null;
  }, [transaction.serviceType]);

  // Check if amount matches total due
  const isAmountMatched = useCallback(() => {
    return transaction.moneyInserted >= transaction.totalDue;
  }, [transaction.moneyInserted, transaction.totalDue]);

  // Calculate money to dispense
  const getMoneyToDispense = useCallback(() => {
    return transaction.selectedAmount || 0;
  }, [transaction.selectedAmount]);

  const value = {
    transaction,
    startTransaction,
    setSelectedAmount,
    setIncludeFee,
    setSelectedDispenseDenominations,
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
