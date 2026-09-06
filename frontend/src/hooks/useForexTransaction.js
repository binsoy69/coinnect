import { useForex } from "../context/ForexContext";

// One provider owns all subscriptions and authoritative transaction state.
export function useForexTransaction() {
  return useForex().api;
}
