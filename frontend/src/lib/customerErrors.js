const messages = {
  FEE_EXCEEDS_AMOUNT: "Fee exceeds amount",
  INSUFFICIENT_STOCK: "Insufficient stock",
  VALIDATION_ERROR: "Check your transaction details and try again.",
  QUOTE_CHANGED: "Availability has changed. Review the updated quote before continuing.",
  QUOTE_EXPIRED: "Your quote has expired. Check availability again.",
  QUOTE_UNAVAILABLE: "This amount is currently unavailable. Choose another amount.",
  INSUFFICIENT_INVENTORY: "There is not enough cash available for this selection.",
  STORAGE_FULL: "Storage for this denomination is full. Please use another denomination.",
  AUTHENTICATION_FAILED: "The bill could not be verified. Check its condition and try again.",
  UNEXPECTED_DENOMINATION: "This denomination is not accepted for this transaction.",
  COIN_INTAKE_UNAVAILABLE: "Coin intake is unavailable. Check the accepted cash options.",
  NO_BILL_DETECTED: "No bill was detected. Please insert a bill.",
  JAM: "The cash acceptor needs attention. Please ask an operator for assistance.",
  HARDWARE_FAULT: "The kiosk needs attention. Please ask an operator for assistance.",
  LOCKED_OUT: "The kiosk is temporarily unavailable. Please ask an operator for assistance.",
  RATE_EXPIRED: "The exchange rate has expired. Review a new quote.",
  RATE_UNAVAILABLE: "Exchange rates are temporarily unavailable.",
  PAYMENT_GATEWAY_ERROR: "Payment status is being checked. Keep this screen open.",
  NETWORK_ERROR: "Connection unavailable. Keep this screen open while the transaction status is checked.",
};
const fields = {
  mobile_number: "Enter an 11-digit mobile number starting with 09.",
  amount: "Enter a valid whole peso amount within the displayed limit.",
  quote_id: "Check availability again before continuing.",
};
const fallbackMessage = "We could not complete this action. Check the transaction status before trying again.";

// Only explicitly authored messages are safe to render, never arbitrary server text.
export function customerError(error, fallback = fallbackMessage) {
  const detail = error?.detail ?? error;
  const code = detail?.code || detail?.error_code || (typeof detail === "string" ? detail : null);
  const errors = Array.isArray(detail) ? detail : detail?.errors;
  if (code === "VALIDATION_ERROR" || Array.isArray(errors)) {
    const field = errors?.[0]?.field || errors?.[0]?.loc?.at(-1);
    return typeof field === "string" && Object.hasOwn(fields, field) ? fields[field] : messages.VALIDATION_ERROR;
  }
  if (typeof code === "string" && Object.hasOwn(messages, code)) return messages[code];
  const text = typeof detail === "string" ? detail : detail?.message;
  if (Object.values(messages).includes(text) || Object.values(fields).includes(text) || text === fallbackMessage) return text;
  if (detail?.name === "TypeError" || detail?.name === "TimeoutError" || detail?.name === "AbortError") return messages.NETWORK_ERROR;
  return fallback;
}

export function customerFailure(data, status) {
  const error = new Error(customerError(data));
  error.code = data?.detail?.code || data?.code;
  error.errors = data?.detail?.errors;
  error.status = status;
  return error;
}
