import { useEffect, useRef } from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";
import { TransactionProvider } from "../context/TransactionContext";
import { ForexProvider } from "../context/ForexContext";
import WarningScreen from "../pages/money-converter/WarningScreen";
import { useBackendTransaction } from "./useBackendTransaction";
import { useForexTransaction } from "./useForexTransaction";

const subscribe = vi.fn();
const unsubscribe = vi.fn();

vi.mock("../context/WebSocketContext", () => ({
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

function ConverterStateProbe() {
  const starter = useBackendTransaction();
  const observer = useBackendTransaction();
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    starter.startBackendTransaction("coin-to-bill", 100, [100]);
  }, [starter]);

  return (
    <span>
      {observer.backendState
        ? `${observer.transactionId}:${observer.backendState.state}:${observer.backendState.claim_ticket_code}`
        : "waiting"}
    </span>
  );
}

function ForexStateProbe() {
  const starter = useForexTransaction();
  const observer = useForexTransaction();
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    starter.startForexBackendTransaction("usd-to-php", 10);
  }, [starter]);

  return (
    <span>
      {observer.backendState
        ? `${observer.transactionId}:${observer.backendState.state}:${observer.backendState.claim_ticket_code}`
        : "waiting"}
    </span>
  );
}

test("money-converter hook instances share terminal backend state", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((url, options = {}) => {
    if (String(url).includes("/admin/fees")) {
      return jsonResponse({});
    }
    if (
      String(url).endsWith("/transaction/") &&
      options.method === "POST"
    ) {
      return jsonResponse({
        transaction_id: "money-tx-1",
        inserted_amount: 100,
        state: "ERROR",
        claim_ticket_code: "CLAIM123",
        shortfall: 100,
      });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  });

  render(
    <TransactionProvider>
      <ConverterStateProbe />
    </TransactionProvider>
  );

  expect(
    await screen.findByText("money-tx-1:ERROR:CLAIM123")
  ).toBeInTheDocument();
});

test("forex hook instances share transaction ID and terminal backend state", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((url, options = {}) => {
    if (String(url).endsWith("/forex/rates")) {
      return jsonResponse({ rates: { USD: 58, EUR: 62 }, online: true });
    }
    if (
      String(url).endsWith("/forex/transaction") &&
      options.method === "POST"
    ) {
      return jsonResponse({
        transaction_id: "forex-tx-1",
        state: "ERROR",
        claim_ticket_code: "FXCLAIM1",
        shortfall: 10,
      });
    }
    throw new Error(`Unexpected fetch: ${url}`);
  });

  render(
    <ForexProvider>
      <ForexStateProbe />
    </ForexProvider>
  );

  expect(
    await screen.findByText("forex-tx-1:ERROR:FXCLAIM1")
  ).toBeInTheDocument();
});

test("warning screen does not report an amount mismatch without a transaction reference", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation((url) => {
    if (String(url).includes("/admin/fees")) {
      return jsonResponse({});
    }
    throw new Error(`Unexpected fetch: ${url}`);
  });

  render(
    <TransactionProvider>
      <MemoryRouter initialEntries={["/money-converter/coin-to-bill/warning"]}>
        <Routes>
          <Route
            path="/money-converter/:type/warning"
            element={<WarningScreen />}
          />
        </Routes>
      </MemoryRouter>
    </TransactionProvider>
  );

  expect(
    screen.getByText("Transaction Status Unavailable")
  ).toBeInTheDocument();
  expect(
    screen.queryByText(/does not match the selected transaction/i)
  ).not.toBeInTheDocument();
});
