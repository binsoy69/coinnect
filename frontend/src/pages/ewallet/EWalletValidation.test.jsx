import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import EWalletMobileScreen from "./EWalletMobileScreen";
import EWalletNameScreen from "./EWalletNameScreen";
import EWalletConfirmScreen from "./EWalletConfirmScreen";
import { ROUTES, getEWalletRoute } from "../../constants/routes";

const wallet = vi.hoisted(() => ({ ewallet: {}, setMobileNumber: vi.fn(), getEWalletConfig: () => ({ name: "GCash", displayName: "Cash In" }), getProviderStyles: () => ({}), startBackendTransaction: vi.fn(), acceptPolicy: vi.fn() }));
vi.mock("../../context/EWalletContext", () => ({ useEWallet: () => wallet }));
beforeEach(() => {
  wallet.ewallet = { provider: "gcash", serviceType: "gcash-cash-in", mobileNumber: "5", totalDue: 100, quote: { quote_id: "q" }, policyAccepted: true };
  wallet.setMobileNumber.mockClear();
  wallet.startBackendTransaction.mockClear();
});
test("short mobile cannot advance and the saved number remains editable", () => {
  render(<MemoryRouter><EWalletMobileScreen /></MemoryRouter>);
  expect(screen.getByRole("textbox", { name: "Mobile number" })).toHaveTextContent("5");
  expect(screen.getByRole("alert")).toHaveTextContent("11-digit");
  expect(screen.getByRole("button", { name: "Proceed" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Proceed" }));
  expect(wallet.setMobileNumber).not.toHaveBeenCalled();
});
test("confirmation does not display names and blocks invalid mobile", () => {
  wallet.ewallet.accountName = "coinnect";
  render(<MemoryRouter><EWalletConfirmScreen /></MemoryRouter>);
  expect(screen.queryByText(/Account Name/)).not.toBeInTheDocument();
  expect(screen.queryByText("coinnect")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Proceed" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Edit mobile number" })).toBeEnabled();
});
test("legacy name route redirects to mobile", () => {
  render(<MemoryRouter initialEntries={["/legacy"]}><Routes>
    <Route path="/legacy" element={<EWalletNameScreen />} />
    <Route path={getEWalletRoute(ROUTES.EWALLET_MOBILE, "gcash-cash-in")} element={<p>Mobile entry</p>} />
  </Routes></MemoryRouter>);
  expect(screen.getByText("Mobile entry")).toBeInTheDocument();
});
