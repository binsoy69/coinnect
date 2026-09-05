import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { useEffect, useRef } from "react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import { TransactionProvider, useTransaction } from "../../context/TransactionContext";
import SelectAmountScreen from "./SelectAmountScreen";
import ConfirmationScreen from "./ConfirmationScreen";
import PayoutReapprovalModal from "../../components/transaction/PayoutReapprovalModal";
import InactivityWarningModal from "../../components/transaction/InactivityWarningModal";
import { useBackendTransaction } from "../../hooks/useBackendTransaction";

const subscribe = vi.fn();
const unsubscribe = vi.fn();

vi.mock("../../context/WebSocketContext", () => ({
  useWebSocket: () => ({
    subscribe,
    unsubscribe,
    isConnected: true,
  }),
}));

function jsonResponse(data, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  });
}

function ConfirmationTestWrapper({ initialQuote = null }) {
  const { setSelectedAmount, setCurrentQuote } = useTransaction();
  const initialized = useRef(false);

  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      setSelectedAmount(100);
      if (initialQuote) {
        setCurrentQuote(initialQuote);
      }
    }
  }, [setSelectedAmount, setCurrentQuote, initialQuote]);

  return <ConfirmationScreen />;
}

describe("Money Converter Flow - Tasks 8 & 9", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it("SelectAmountScreen disables unavailable amounts and shows reasons", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
      if (String(url).includes("/admin/fees")) {
        return jsonResponse({ fee_bill_to_bill: 10 });
      }
      if (String(url).includes("/transaction/options?type=bill-to-bill")) {
        return jsonResponse({
          service_type: "bill-to-bill",
          fee: 10,
          options: [
            { amount: 20, enabled: false, reason: "Fee exceeds amount" },
            { amount: 50, enabled: true, reason: null },
            { amount: 100, enabled: true, reason: null },
            { amount: 200, enabled: false, reason: "Insufficient stock" },
            { amount: 500, enabled: true, reason: null },
            { amount: 1000, enabled: true, reason: null },
          ],
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(
      <TransactionProvider>
        <MemoryRouter initialEntries={["/money-converter/bill-to-bill/select-amount"]}>
          <Routes>
            <Route
              path="/money-converter/:type/select-amount"
              element={<SelectAmountScreen />}
            />
          </Routes>
        </MemoryRouter>
      </TransactionProvider>
    );

    // Wait for options to load
    await waitFor(() => {
      expect(screen.getByText("Fee exceeds amount")).toBeInTheDocument();
      expect(screen.getByText("Insufficient stock")).toBeInTheDocument();
    });

    // 20 and 200 buttons should be disabled
    const btn20 = screen.getByText("20").closest("button");
    const btn50 = screen.getByText("50").closest("button");
    const btn200 = screen.getByText("200").closest("button");

    expect(btn20).toBeDisabled();
    expect(btn200).toBeDisabled();
    expect(btn50).not.toBeDisabled();
  });

  it("ConfirmationScreen displays substitution notice and starts transaction with quote_id", async () => {
    let startBody = null;

    vi.spyOn(globalThis, "fetch").mockImplementation((url, options = {}) => {
      if (String(url).includes("/admin/fees")) {
        return jsonResponse({});
      }
      if (String(url).includes("/transaction/quote")) {
        return jsonResponse({
          id: "quote-xyz-123",
          service_type: "bill-to-bill",
          input_amount: 100,
          fee: 10,
          total_due: 100,
          payout_amount: 90,
          items: [
            { denom: "PHP_50", value: 50, count: 1, denom_type: "bill" },
            { denom: "PHP_20", value: 20, count: 2, denom_type: "bill" },
          ],
          requested_counts: null,
          is_substitution: true,
          substitution_notice: "Substituted 100 with 50 and 20x2 bills.",
        });
      }
      if (String(url).endsWith("/transaction/") && options.method === "POST") {
        startBody = JSON.parse(options.body);
        return jsonResponse({
          transaction_id: "tx-conv-1",
          state: "WAITING_FOR_BILL",
          total_due: 100,
          payout_amount: 90,
          fee: 10,
          inserted_amount: 0,
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(
      <TransactionProvider>
        <MemoryRouter initialEntries={["/money-converter/bill-to-bill/confirmation"]}>
          <Routes>
            <Route
              path="/money-converter/:type/confirmation"
              element={<ConfirmationTestWrapper />}
            />
          </Routes>
        </MemoryRouter>
      </TransactionProvider>
    );

    // Substitution notice should appear
    await waitFor(() => {
      expect(screen.getByText(/Stock Substitution Notice/i)).toBeInTheDocument();
      expect(
        screen.getByText(/Substituted 100 with 50 and 20x2 bills/i)
      ).toBeInTheDocument();
    });

    // Breakdown should render items
    expect(screen.getByText(/1x/)).toBeInTheDocument();
    expect(screen.getByText(/2x/)).toBeInTheDocument();

    // Click Proceed
    const proceedBtn = screen.getByRole("button", { name: "Proceed" });
    fireEvent.click(proceedBtn);

    await waitFor(() => {
      expect(startBody).not.toBeNull();
      expect(startBody.quote_id).toBe("quote-xyz-123");
    });
  });

  it("PayoutReapprovalModal shows revised breakdown and triggers approve or claim", () => {
    const onApprove = vi.fn();
    const onRequestClaim = vi.fn();

    const pendingQuote = {
      id: "pending-q-456",
      payout_amount: 80,
      substitution_notice: "Stock dropped. Adjusted to 20x4.",
      items: [
        { denom: "PHP_20", value: 20, count: 4, denom_type: "bill" },
      ],
    };

    render(
      <PayoutReapprovalModal
        pendingQuote={pendingQuote}
        onApprove={onApprove}
        onRequestClaim={onRequestClaim}
      />
    );

    expect(screen.getByText("Payout Adjustment Required")).toBeInTheDocument();
    expect(screen.getByText("Stock dropped. Adjusted to 20x4.")).toBeInTheDocument();
    expect(screen.getByText(/4x/)).toBeInTheDocument();

    // Test approve button
    const approveBtn = screen.getByRole("button", { name: "Accept Revised Payout" });
    fireEvent.click(approveBtn);
    expect(onApprove).toHaveBeenCalledWith("pending-q-456");

    // Test claim button
    const claimBtn = screen.getByRole("button", { name: "Request Cash Claim" });
    fireEvent.click(claimBtn);
    expect(onRequestClaim).toHaveBeenCalledTimes(1);
  });

  it("InactivityWarningModal triggers onKeepAlive when button clicked", async () => {
    const onKeepAlive = vi.fn();

    render(
      <InactivityWarningModal
        active={true}
        onKeepAlive={onKeepAlive}
      />
    );

    expect(await screen.findByText("Are you still there?")).toBeInTheDocument();
    const keepAliveBtn = screen.getByRole("button", { name: /I'm Still Here/i });
    fireEvent.click(keepAliveBtn);
    expect(onKeepAlive).toHaveBeenCalledTimes(1);
  });

  it("useBackendTransaction discards out-of-order snapshots based on monotonic revision", () => {
    sessionStorage.setItem("converterTransactionId", "tx-rev-1");
    let capturedHandler = null;
    subscribe.mockImplementation((eventType, cb) => {
      if (eventType === "CONVERTER_SNAPSHOT") {
        capturedHandler = cb;
      }
    });

    function RevisionProbe() {
      const { backendState } = useBackendTransaction();
      return <span data-testid="rev">{backendState?.revision ?? "none"}</span>;
    }

    render(
      <TransactionProvider>
        <RevisionProbe />
      </TransactionProvider>
    );

    expect(capturedHandler).not.toBeNull();

    // Fire revision 2
    act(() => {
      capturedHandler({
        payload: {
          transaction_id: "tx-rev-1",
          inserted_amount: 20,
          revision: 2,
          state: "WAITING_FOR_BILL",
        },
      });
    });

    expect(screen.getByTestId("rev")).toHaveTextContent("2");

    // Fire older revision 1 - should be ignored
    act(() => {
      capturedHandler({
        payload: {
          transaction_id: "tx-rev-1",
          inserted_amount: 20,
          revision: 1,
          state: "WAITING_FOR_BILL",
        },
      });
    });

    // Still revision 2!
    expect(screen.getByTestId("rev")).toHaveTextContent("2");

    // Fire newer revision 3 - should be accepted
    act(() => {
      capturedHandler({
        payload: {
          transaction_id: "tx-rev-1",
          inserted_amount: 20,
          revision: 3,
          state: "WAITING_FOR_CONFIRMATION",
        },
      });
    });

    expect(screen.getByTestId("rev")).toHaveTextContent("3");
  });
});
