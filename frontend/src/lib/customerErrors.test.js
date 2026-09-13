import { customerError, customerFailure } from "./customerErrors";
import { mobileError, amountError, walletValidation } from "./validation";

test.each(["5", "08123456789", "0912345678", "091234567890", "09abcdefghi", ""])("rejects mobile %s", value => {
  expect(mobileError(value)).not.toBe("");
});
test("valid mobile and whole amount", () => {
  expect(mobileError("09123456789")).toBe("");
  expect(amountError("50000")).toBe("");
});
test.each(["0", "-1", "1.5", "50001", "12abc", "Infinity", ""])("rejects amount %s", value => {
  expect(amountError(value)).not.toBe("");
});
test("wallet requires a quote, mobile and acceptance, but no name", () => {
  const wallet = { serviceType: "gcash-cash-in", totalDue: 100, mobileNumber: "09123456789", policyAccepted: true, quote: { quote_id: "q" } };
  expect(walletValidation(wallet)).toBe("");
  expect(walletValidation({ ...wallet, mobileNumber: "5" })).toMatch(/11-digit/);
  expect(walletValidation({ ...wallet, quote: null })).toMatch(/availability/);
  expect(walletValidation({ ...wallet, serviceType: "maya-cash-out", mobileNumber: "", policyAccepted: false })).toBe("");
});
test.each(["String should match pattern '^09\\d{9}$'", "Traceback /private/server.py", { message: "secret stack" }, null])("unknown errors never echo content: %j", error => {
  expect(customerError(error)).toBe("We could not complete this action. Check the transaction status before trying again.");
});
test("validation fields and lifecycle codes survive normalization", () => {
  const data = { detail: { code: "VALIDATION_ERROR", errors: [{ loc: ["body", "mobile_number"], msg: "raw regex", input: "5" }] } };
  expect(customerError(data)).toMatch(/11-digit/);
  const error = customerFailure({ detail: { code: "QUOTE_EXPIRED", message: "private" } }, 409);
  expect(error.code).toBe("QUOTE_EXPIRED");
  expect(error.status).toBe(409);
  expect(customerError(error)).toMatch(/quote has expired/);
});
