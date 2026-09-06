import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import EWalletSummaryScreen from "./EWalletSummaryScreen";
import EWalletSessionStatus from "../../components/ewallet/EWalletSessionStatus";

const wallet = vi.hoisted(() => ({ ewallet: {}, resetTransaction: vi.fn(), continueSession: vi.fn().mockResolvedValue({}), cancelBackendTransaction: vi.fn().mockResolvedValue({}) }));
vi.mock("../../context/EWalletContext", () => ({ useEWallet: () => wallet }));

beforeEach(() => {
  wallet.ewallet = { backendState: { transaction_id: "test", state: "ACCEPTING_CASH", direction: "cash-in", total_due: 100, inserted_amount: 50, deadline: new Date(Date.now() + 20000).toISOString(), can_cancel: false } };
});

test.each(["CANCELLED", "ABANDONED_RETAINED", "CLAIM_REQUIRED", "DISBURSEMENT_PENDING"])("%s never displays successful completion", state => {
  wallet.ewallet.backendState.state = state;
  render(<MemoryRouter><EWalletSummaryScreen /></MemoryRouter>);
  expect(screen.queryByText("Transaction complete")).not.toBeInTheDocument();
});

test("funded session hides cancellation and warns before partial inactivity expires", () => {
  render(<EWalletSessionStatus />);
  expect(screen.queryByRole("button", { name: "Cancel before payment" })).not.toBeInTheDocument();
  expect(screen.getByText(/partial cash is retained/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
  expect(wallet.continueSession).toHaveBeenCalled();
});

test("unpaid QR offers cancel but cannot extend its deadline", () => {
  Object.assign(wallet.ewallet.backendState, { state: "WAITING_FOR_PAYMENT", direction: "cash-out", can_cancel: true, amount: 100, fee: 15, transfer_amount: 85 });
  render(<EWalletSessionStatus />);
  expect(screen.getByRole("button", { name: "Cancel before payment" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Continue" })).not.toBeInTheDocument();
  expect(screen.getByText(/Payment status will be checked/)).toBeInTheDocument();
  expect(screen.getByText(/Amount paid: ₱100 · Fee: ₱15 · Cash received: ₱85/)).toBeInTheDocument();
});
