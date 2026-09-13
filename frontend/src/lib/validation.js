export function mobileError(value) {
  return /^09[0-9]{9}$/.test(value || "") ? "" : "Enter an 11-digit mobile number starting with 09.";
}

export function amountError(value, maximum = 50000) {
  if (!/^[0-9]+$/.test(String(value)) || !Number.isSafeInteger(Number(value)) || Number(value) <= 0) {
    return "Enter a whole peso amount greater than zero.";
  }
  return Number(value) > maximum ? `Enter an amount no greater than ₱${maximum.toLocaleString()}.` : "";
}

export function walletValidation(wallet) {
  if (amountError(wallet.totalDue, wallet.maxAmount)) return amountError(wallet.totalDue, wallet.maxAmount);
  if (wallet.serviceType?.endsWith("cash-in")) {
    if (mobileError(wallet.mobileNumber)) return mobileError(wallet.mobileNumber);
    if (!wallet.policyAccepted) return "Accept the cash-in rules before continuing.";
  }
  if (!wallet.quote?.quote_id) return "Check the amount and availability again before continuing.";
  return "";
}
