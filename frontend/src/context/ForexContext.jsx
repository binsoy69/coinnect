/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback } from 'react';
import {
  FOREX_CONFIG,
  MOCK_EXCHANGE_RATES,
  CURRENCIES,
  calculateConversion,
  isForeignToPhp,
} from '../constants/forexData';

// Default state for forex transaction
const DEFAULT_FOREX_STATE = {
  serviceType: null,
  fromCurrency: null,
  toCurrency: null,
  exchangeRate: 0,
  rateLocked: false,
  selectedAmount: null,      // Amount in the "selection" currency (foreign for both directions)
  convertedAmount: 0,        // Converted amount before fee
  feePercentage: 5,
  feeAmount: 0,
  amountToDispense: 0,       // Final amount after fee deduction
  totalDue: 0,               // Total amount user needs to insert
  insertedCounts: {},        // { denomination: count }
  moneyInserted: 0,          // Total value of inserted money
};

const ForexContext = createContext(null);

export function ForexProvider({ children }) {
  const [forex, setForex] = useState(DEFAULT_FOREX_STATE);

  // Initialize forex transaction with service type
  const startForexTransaction = useCallback((serviceType) => {
    const config = FOREX_CONFIG[serviceType];
    if (!config) return;

    const { fromCurrency, toCurrency, feePercentage } = config;

    // Get the exchange rate
    let exchangeRate;
    if (fromCurrency === CURRENCIES.PHP) {
      // PHP to foreign: use inverse rate
      exchangeRate = 1 / MOCK_EXCHANGE_RATES[toCurrency];
    } else {
      // Foreign to PHP
      exchangeRate = MOCK_EXCHANGE_RATES[fromCurrency];
    }

    setForex({
      ...DEFAULT_FOREX_STATE,
      serviceType,
      fromCurrency,
      toCurrency,
      exchangeRate,
      feePercentage,
    });
  }, []);

  // Set selected amount and calculate conversion
  const setSelectedAmount = useCallback((amount) => {
    setForex(prev => {
      const config = FOREX_CONFIG[prev.serviceType];
      if (!config) return prev;

      const { fromCurrency, toCurrency, feePercentage } = config;

      // For foreign→PHP: amount is in foreign currency
      // For PHP→foreign: amount is the foreign currency amount to receive
      if (isForeignToPhp(prev.serviceType)) {
        // Foreign to PHP: user selects foreign amount, gets PHP
        const conversion = calculateConversion(amount, fromCurrency, toCurrency, feePercentage);
        return {
          ...prev,
          selectedAmount: amount,
          convertedAmount: conversion.convertedAmount,
          feeAmount: conversion.feeAmount,
          amountToDispense: conversion.amountToDispense,
          totalDue: amount, // User inserts the foreign amount
        };
      } else {
        // PHP to foreign: user selects foreign amount to receive
        // Calculate how much PHP they need to insert
        const foreignToPhpRate = MOCK_EXCHANGE_RATES[toCurrency];
        const phpNeeded = Math.ceil(amount * foreignToPhpRate);
        const feeAmount = Math.round(phpNeeded * (feePercentage / 100));
        const totalDue = phpNeeded + feeAmount;

        return {
          ...prev,
          selectedAmount: amount,           // Foreign amount to receive
          convertedAmount: phpNeeded,       // PHP equivalent (before fee)
          feeAmount,                        // Fee in PHP
          amountToDispense: amount,         // Foreign amount to dispense
          totalDue,                         // Total PHP to insert
        };
      }
    });
  }, []);

  // Lock the exchange rate (called when user confirms)
  const lockRate = useCallback(() => {
    setForex(prev => ({
      ...prev,
      rateLocked: true,
    }));
  }, []);

  // Unlock the rate (if user goes back)
  const unlockRate = useCallback(() => {
    setForex(prev => ({
      ...prev,
      rateLocked: false,
    }));
  }, []);

  // Refresh exchange rate (only if not locked)
  const refreshRate = useCallback(() => {
    setForex(prev => {
      if (prev.rateLocked) return prev;

      const config = FOREX_CONFIG[prev.serviceType];
      if (!config) return prev;

      const { fromCurrency, toCurrency } = config;

      // Get fresh rate (in real app, would fetch from API)
      let exchangeRate;
      if (fromCurrency === CURRENCIES.PHP) {
        exchangeRate = 1 / MOCK_EXCHANGE_RATES[toCurrency];
      } else {
        exchangeRate = MOCK_EXCHANGE_RATES[fromCurrency];
      }

      // Recalculate if amount is selected
      if (prev.selectedAmount) {
        if (isForeignToPhp(prev.serviceType)) {
          const conversion = calculateConversion(
            prev.selectedAmount,
            fromCurrency,
            toCurrency,
            prev.feePercentage
          );
          return {
            ...prev,
            exchangeRate,
            convertedAmount: conversion.convertedAmount,
            feeAmount: conversion.feeAmount,
            amountToDispense: conversion.amountToDispense,
          };
        } else {
          const foreignToPhpRate = MOCK_EXCHANGE_RATES[toCurrency];
          const phpNeeded = Math.ceil(prev.selectedAmount * foreignToPhpRate);
          const feeAmount = Math.round(phpNeeded * (prev.feePercentage / 100));
          const totalDue = phpNeeded + feeAmount;

          return {
            ...prev,
            exchangeRate,
            convertedAmount: phpNeeded,
            feeAmount,
            totalDue,
          };
        }
      }

      return { ...prev, exchangeRate };
    });
  }, []);

  // Update inserted money counts
  const updateInsertedCount = useCallback((denom, count) => {
    setForex(prev => {
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
    setForex(prev => {
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

  // Reset forex transaction to initial state
  const resetForexTransaction = useCallback(() => {
    setForex(DEFAULT_FOREX_STATE);
  }, []);

  // Get current forex service config
  const getForexConfig = useCallback(() => {
    return FOREX_CONFIG[forex.serviceType] || null;
  }, [forex.serviceType]);

  // Check if inserted amount matches total due
  const isAmountMatched = useCallback(() => {
    return forex.moneyInserted >= forex.totalDue;
  }, [forex.moneyInserted, forex.totalDue]);

  // Get the amount to dispense based on actual inserted amount
  const getActualDispenseAmount = useCallback(() => {
    if (isForeignToPhp(forex.serviceType)) {
      // Foreign→PHP: Dispense PHP based on what was inserted
      const config = FOREX_CONFIG[forex.serviceType];
      if (!config) return 0;

      const conversion = calculateConversion(
        forex.moneyInserted,
        config.fromCurrency,
        config.toCurrency,
        forex.feePercentage
      );
      return conversion.amountToDispense;
    } else {
      // PHP→Foreign: Dispense the selected foreign amount
      return forex.amountToDispense;
    }
  }, [forex.serviceType, forex.moneyInserted, forex.feePercentage, forex.amountToDispense]);

  const value = {
    forex,
    startForexTransaction,
    setSelectedAmount,
    lockRate,
    unlockRate,
    refreshRate,
    updateInsertedCount,
    addInsertedMoney,
    resetForexTransaction,
    getForexConfig,
    isAmountMatched,
    getActualDispenseAmount,
  };

  return (
    <ForexContext.Provider value={value}>
      {children}
    </ForexContext.Provider>
  );
}

export function useForex() {
  const context = useContext(ForexContext);
  if (!context) {
    throw new Error('useForex must be used within a ForexProvider');
  }
  return context;
}

export default ForexContext;
