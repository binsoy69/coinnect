import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { ForexProvider, useForex } from "./ForexContext";

const socket = vi.hoisted(() => ({ listeners: new Map(), connected: true,
  subscribe: vi.fn((name, callback) => socket.listeners.set(name, callback)),
  unsubscribe: vi.fn((name, callback) => { if (socket.listeners.get(name) === callback) socket.listeners.delete(name); }),
}));
vi.mock("./WebSocketContext", () => ({ useWebSocket: () => ({ ...socket, isConnected: socket.connected }) }));
const quote = { quote_id: "quote-one", service_type: "php-to-usd", selected_amount: 10,
  from_currency: "PHP", to_currency: "USD", rate: 1/60, php_rate: "60", converted_amount: 600,
  fee_amount: 30, fee_percentage: 5, input_amount: 630, output_amount: 10 };
const snapshot = { transaction_id: "fx-one", type: "forex-php-to-usd", quote, revision: 2,
  state: "WAITING_FOR_BILL", inserted_amount: 500, inserted_denominations: { PHP_500: 1 } };
const response = data => Promise.resolve({ ok: true, json: async () => data });
function Probe() {
  const fx = useForex();
  return <><output>{fx.transactionId || "none"}:{fx.forex.moneyInserted}:{fx.forex.totalDue}:{fx.backendState?.state || "none"}</output>
    <button onClick={() => fx.refreshForexTransaction().catch(() => {})}>Refresh</button>
    <button onClick={() => fx.startForexBackendTransaction().catch(() => {})}>Retry start</button>
    <button onClick={() => fx.continueForexTransaction().catch(() => {})}>Continue</button>
    {fx.error && <p role="alert">{fx.error}</p>}</>;
}
function stub(getSnapshot = () => snapshot) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(url => {
    if (String(url).endsWith("/rates")) return response({ rates: { USD:60, EUR:64 }, online:true, valid:true });
    return response(getSnapshot());
  });
}
function restore() { sessionStorage.setItem("forexTransaction", "fx-one"); }

test("reload restores authoritative accepted cash and refresh retains the reference", async () => {
  restore(); stub();
  render(<ForexProvider><Probe /></ForexProvider>);
  expect(await screen.findByText("fx-one:500:630:WAITING_FOR_BILL")).toBeInTheDocument();
  await userEvent.click(screen.getByText("Refresh"));
  expect(sessionStorage.getItem("forexTransaction")).toBe("fx-one");
  expect(screen.getByText("fx-one:500:630:WAITING_FOR_BILL")).toBeInTheDocument();
});

test("stale snapshots and duplicate bill notifications cannot inflate cash", async () => {
  restore(); let data = snapshot; stub(() => data);
  render(<ForexProvider><Probe /></ForexProvider>);
  await screen.findByText("fx-one:500:630:WAITING_FOR_BILL");
  expect(socket.listeners.has("BILL_STORED")).toBe(false);
  data = { ...snapshot, revision:1, inserted_amount:1000 };
  await act(async () => { socket.listeners.get("TRANSACTION_STATE_CHANGED")({payload:{transaction_id:"fx-one"}}); });
  expect(screen.getByText("fx-one:500:630:WAITING_FOR_BILL")).toBeInTheDocument();
});

test("claim events retrieve the terminal snapshot without dropping the ID", async () => {
  restore(); let data = snapshot; stub(() => data);
  render(<ForexProvider><Probe /></ForexProvider>);
  await screen.findByText("fx-one:500:630:WAITING_FOR_BILL");
  data = { ...snapshot, revision:3, state:"CLAIM_REQUIRED", claim:{claim_ticket_code:"ONE",items:[]} };
  await act(async () => { socket.listeners.get("CLAIM_TICKET")({payload:{transaction_id:"fx-one"}}); });
  expect(await screen.findByText("fx-one:500:630:CLAIM_REQUIRED")).toBeInTheDocument();
  expect(sessionStorage.getItem("forexTransaction")).toBe("fx-one");
});

test("lost start response retries the same persisted idempotency key", async () => {
  const pending = {quote_id:"quote-one",idempotency_key:"stable-start-key"};
  sessionStorage.setItem("forexStart",JSON.stringify(pending));
  let attempts=0; const bodies=[];
  vi.spyOn(globalThis,"fetch").mockImplementation((url,options={}) => {
    if (String(url).endsWith("/rates")) return response({rates:{},valid:false});
    if (options.method === "POST") {
      bodies.push(JSON.parse(options.body)); attempts++;
      if(attempts===1) return Promise.reject(new Error("Response lost"));
    }
    return response(snapshot);
  });
  render(<ForexProvider><Probe /></ForexProvider>);
  await screen.findByRole("alert");
  expect(JSON.parse(sessionStorage.getItem("forexStart"))).toEqual(pending);
  await userEvent.click(screen.getByText("Retry start"));
  await screen.findByText("fx-one:500:630:WAITING_FOR_BILL");
  expect(bodies).toEqual([pending,pending]);
});

test("Continue uses the active transaction endpoint and accepts server deadline", async () => {
  restore(); const fetch=stub(); render(<ForexProvider><Probe /></ForexProvider>);
  await screen.findByText("fx-one:500:630:WAITING_FOR_BILL");
  await userEvent.click(screen.getByText("Continue"));
  await waitFor(() => expect(fetch.mock.calls.some(([url,options]) => String(url).endsWith("/fx-one/continue") && options.method === "POST")).toBe(true));
});
