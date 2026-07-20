import { render, screen, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import App from "./App";
import { TransactionProvider } from "./context/TransactionContext";
import { ForexProvider } from "./context/ForexContext";
import { EWalletProvider } from "./context/EWalletContext";

let wsListener = null;

vi.mock("./context/WebSocketContext", async (importOriginal) => {
  const original = await importOriginal();
  return {
    ...original,
    useWebSocket: () => ({
      isConnected: true,
      subscribe: vi.fn((event, callback) => {
        if (event === "STATE_CHANGE") {
          wsListener = callback;
        }
      }),
      unsubscribe: vi.fn(),
      sendMessage: vi.fn(),
    }),
  };
});

test("redirects to admin inventory when STATE_CHANGE maintenance event is received", async () => {
  // Mock global fetch for the inventory screen fetch call on mount
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({
      startup_checks: { performed: true, has_errors: false, errors: {} },
      bill_storage_counts: {},
      bill_dispenser_counts: {},
      coin_counts: {},
      alerts: [],
      adjustments: [],
    }),
  });

  render(
    <MemoryRouter initialEntries={["/"]}>
      <TransactionProvider>
        <ForexProvider>
          <EWalletProvider>
            <App />
          </EWalletProvider>
        </ForexProvider>
      </TransactionProvider>
    </MemoryRouter>
  );

  expect(wsListener).not.toBeNull();

  act(() => {
    wsListener({
      type: "STATE_CHANGE",
      payload: {
        mode: "maintenance",
        admin_session: {
          token: "rfid-token-123",
          session_id: "rfid-session-123",
          expires_at: "2026-07-08T16:00:00Z",
        },
      },
    });
  });

  expect(sessionStorage.getItem("coinnect_admin_token")).toBe("rfid-token-123");
  expect(await screen.findByText("Maintenance mode")).toBeInTheDocument();
});
