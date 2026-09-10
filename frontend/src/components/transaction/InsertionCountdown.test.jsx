import { act, render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import InsertMoneyScreen from "../../pages/money-converter/InsertMoneyScreen";
import EWalletIntakeScreen from "../ewallet/EWalletIntakeScreen";
import ForexInsertMoneyScreen from "../../pages/forex/ForexInsertMoneyScreen";

const mocks = vi.hoisted(() => ({ converter: {}, wallet: {}, forex: {}, acceptance: {}, continueSession: vi.fn() }));
vi.mock("../../context/TransactionContext", () => ({ useTransaction: () => mocks.converter }));
vi.mock("../../hooks/useBackendTransaction", () => ({ useBackendTransaction: () => ({ backendState: mocks.converter.backendState }) }));
vi.mock("../../context/EWalletContext", () => ({ useEWallet: () => ({ ...mocks.wallet, continueSession: mocks.continueSession }) }));
vi.mock("../../context/ForexContext", () => ({ useForex: () => mocks.forex }));
vi.mock("../../hooks/useBillAcceptance", () => ({ useBillAcceptance: () => mocks.acceptance }));
const epoch = Date.parse("2026-09-07T12:00:00Z");
const timing = { server_time: new Date(epoch).toISOString(), deadline: new Date(epoch + 90000).toISOString(), expires_at: new Date(epoch + 90000).toISOString(), inactivity_timeout_seconds: 90 };
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "setTimeout", "clearTimeout", "Date", "performance"] });
  vi.setSystemTime(epoch);
  mocks.acceptance = { isSorting: false, lastError: null, clearError: vi.fn() };
  mocks.converter = { transaction: { moneyInserted: 0, totalDue: 100, insertedCounts: {} }, backendState: { ...timing, state: "WAITING_FOR_BILL" }, getServiceConfig: () => ({ insertType: "bill", insertCounters: [20, 50, 100], shortName: "Bill to bill" }), isAmountMatched: () => false };
  mocks.wallet = { ewallet: { serviceType: "gcash", backendState: { ...timing, state: "ACCEPTING_CASH", direction: "cash-in", inserted_amount: 50, total_due: 100, allowed_intake: { bills: [20, 50], coins_enabled: true } } } };
  mocks.forex = { forex: { moneyInserted: 0, fromCurrency: "USD", totalDue: 10 }, backendState: { ...timing, state: "WAITING_FOR_BILL" }, getForexConfig: () => ({ insertHeading: "Insert bills", acceptDenominations: [10, 50] }) };
  mocks.continueSession.mockReset().mockResolvedValue({});
});
afterEach(() => vi.useRealTimers());
const mount = ui => render(<MemoryRouter>{ui}</MemoryRouter>);

test.each(["bill", "coin"])("converter %s intake displays countdown", medium => {
  mocks.converter.getServiceConfig = () => ({ insertType: medium, insertCounters: [20] });
  mount(<InsertMoneyScreen />);
  expect(screen.getByRole("timer")).toHaveTextContent("90s");
  act(() => vi.advanceTimersByTime(1000));
  expect(screen.getByRole("timer")).toHaveTextContent("89s");
});
test.each(["gcash", "maya"])("%s preserves deadline when switching bills and coins", provider => {
  mocks.wallet.ewallet.serviceType = provider;
  const view = mount(<EWalletIntakeScreen medium="bills" />);
  act(() => vi.advanceTimersByTime(10000));
  view.rerender(<MemoryRouter><EWalletIntakeScreen medium="coins" /></MemoryRouter>);
  expect(screen.getByRole("timer")).toHaveTextContent("80s");
});
test("forex bill intake uses the shared progress bar", () => {
  mount(<ForexInsertMoneyScreen />);
  expect(screen.getByRole("timer")).toHaveTextContent("90s");
  expect(screen.getByRole("progressbar")).toBeInTheDocument();
});
test("failed Continue keeps the deadline and accepted cash expiry waits for backend", async () => {
  mocks.continueSession.mockRejectedValue(new Error("Offline"));
  mount(<EWalletIntakeScreen medium="bills" />);
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Continue" })));
  expect(screen.getByRole("alert")).toHaveTextContent("Offline");
  act(() => vi.advanceTimersByTime(91000));
  expect(screen.getByRole("timer")).toHaveTextContent("0s");
  expect(screen.getByText("Checking transaction status…")).toBeInTheDocument();
});
test("sorting overlay stays visible and does not locally reset a deadline", () => {
  mocks.acceptance.isSorting = true;
  mount(<InsertMoneyScreen />);
  expect(screen.getByText(/Validating and sorting/)).toBeInTheDocument();
  act(() => vi.advanceTimersByTime(10000));
  expect(screen.getByRole("timer")).toHaveTextContent("80s");
});

test("successful Continue waits for an acknowledged deadline before extending", async () => {
  const view = mount(<EWalletIntakeScreen medium="bills" />);
  act(() => vi.advanceTimersByTime(10000));
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "Continue" })));
  expect(screen.getByRole("timer")).toHaveTextContent("80s");
  Object.assign(mocks.wallet.ewallet.backendState, { server_time: new Date(epoch + 10000).toISOString(), deadline: new Date(epoch + 100000).toISOString() });
  view.rerender(<MemoryRouter><EWalletIntakeScreen medium="bills" /></MemoryRouter>);
  expect(screen.getByRole("timer")).toHaveTextContent("90s");
});

test("rejection and payout reapproval preserve the deadline and blocking dialogs", () => {
  mocks.acceptance.lastError = "AUTHENTICATION_FAILED";
  const view = mount(<InsertMoneyScreen />);
  expect(screen.getByText("Bill Unauthenticated")).toBeInTheDocument();
  act(() => vi.advanceTimersByTime(10000));
  mocks.acceptance.lastError = null;
  mocks.converter.backendState.pending_quote = { items: [], payout_amount: 100 };
  view.rerender(<MemoryRouter><InsertMoneyScreen /></MemoryRouter>);
  expect(screen.getByText("Payout Adjustment Required")).toBeInTheDocument();
  expect(screen.getByRole("timer")).toHaveTextContent("80s");
});
