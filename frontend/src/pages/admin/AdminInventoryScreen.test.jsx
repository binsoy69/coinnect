import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import AdminInventoryScreen from "./AdminInventoryScreen";


const inventory = {
  bill_dispenser_counts: {
    PHP_20: 1, PHP_50: 2, PHP_100: 3, PHP_200: 4, PHP_500: 5,
    PHP_1000: 6, USD_10: 7, USD_50: 8,
    EUR_5: 10, EUR_10: 11,
  },
  coin_counts: { PHP_1: 10, PHP_5: 20, PHP_10: 30, PHP_20: 40 },
  bill_storage_counts: {
    PHP_20: 0, PHP_50: 0, PHP_100: 0, PHP_200: 0,
    PHP_500: 0, PHP_1000: 0, USD: 4, EUR: 5,
  },
  alerts: [],
};


function response(body, ok = true) {
  return { ok, status: ok ? 200 : 401, json: async () => body };
}

test.each(["STANDARD", "EWALLET", "MISSING"])("routes provisional %s claims to the appropriate review", async (sourceKind) => {
  sessionStorage.setItem("coinnect_admin_token", "admin-token");
  const user = userEvent.setup();
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    if (url.endsWith("/inventory/")) return response(inventory);
    if (url.endsWith("/admin/claims")) return response({ claims: [{
      claim_ticket_code: "REVIEW123", transaction_id: "tx-review", source_kind: sourceKind,
      status: "PROVISIONAL", amount: 100, created_at: "2026-09-07T05:00:00",
    }], intake_operations: [{ id: "payout-review", transaction_id: sourceKind === "MISSING" ? "unrelated-tx" : "tx-review", medium: "PAYOUT",
      denomination: "PHP_5", requested_count: 1 }] });
    return response({ adjustments: [], records: [], items: [] });
  });
  render(<MemoryRouter><AdminInventoryScreen /></MemoryRouter>);
  await user.click(await screen.findByRole("button", { name: /Claims Resolution/ }));
  if (sourceKind === "MISSING") {
    await user.click(await screen.findByRole("button", { name: "Review physical counts" }));
    expect(screen.getByRole("alert")).toHaveTextContent("No pending physical operation was found");
    expect(screen.queryByText("Confirm physical cash movement")).not.toBeInTheDocument();
  } else if (sourceKind === "STANDARD") {
    const button = await screen.findByRole("button", { name: "Review physical counts" });
    await user.click(button);
    expect(screen.getByText("Confirm physical cash movement")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirmed PHP_5 pieces dispensed (requested 1)")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Save verified counts" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter inspection notes with at least 5 characters");
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith("/payout-review/reconcile"))).toBe(false);
    await user.type(screen.getByLabelText("Inspection notes"), "Verified one coin");
    await user.click(screen.getByRole("button", { name: "Save verified counts" }));
    expect(fetchMock.mock.calls.some(([url, options]) =>
      url.endsWith("/admin/physical-operations/payout-review/reconcile") && options.method === "POST"
    )).toBe(true);
    expect(screen.getByRole("status")).toHaveTextContent("Physical inspection saved");
    expect(fetchMock.mock.calls.some(([url]) => url.includes("/ewallet/"))).toBe(false);
  } else {
    await user.click(await screen.findByRole("button", { name: "Verify payment status" }));
    expect(fetchMock.mock.calls.some(([url, options]) =>
      url.endsWith("/admin/ewallet/tx-review/reconcile") && options.method === "POST"
    )).toBe(true);
  }
});


test("edits inventory, reviews changes, and saves an absolute count", async () => {
  sessionStorage.setItem("coinnect_admin_token", "admin-token");
  const user = userEvent.setup();
  const fetchMock = vi.spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(response(inventory))
    .mockResolvedValueOnce(response({ adjustments: [] }))
    .mockResolvedValueOnce(response({
      ...inventory,
      bill_dispenser_counts: {
        ...inventory.bill_dispenser_counts,
        PHP_100: 25,
      },
    }))
    .mockResolvedValueOnce(response({ adjustments: [] }));

  render(
    <MemoryRouter>
      <AdminInventoryScreen />
    </MemoryRouter>
  );

  const countInput = await screen.findByLabelText("PHP 100 count");
  await user.clear(countInput);
  await user.type(countInput, "25");
  await user.click(screen.getByRole("button", { name: "Save inventory" }));

  expect(screen.getAllByText("PHP 100").length).toBeGreaterThan(0);
  expect(screen.getByText("3 → 25")).toBeInTheDocument();

  await user.selectOptions(screen.getByLabelText("Adjustment reason"), "REFILL");
  await user.click(screen.getByRole("button", { name: "Confirm changes" }));

  await waitFor(() => {
    const request = JSON.parse(fetchMock.mock.calls[2][1].body);
    expect(request.updates).toEqual([
      {
        location: "BILL_DISPENSER",
        denomination: "PHP_100",
        count: 25,
      },
    ]);
    expect(request.reason).toBe("REFILL");
  });
  expect(await screen.findByText("Inventory updated")).toBeInTheDocument();
});


test("expired session returns to home", async () => {
  sessionStorage.setItem("coinnect_admin_token", "expired");
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    response({ detail: "Admin session expired" }, false)
  );

  render(
    <MemoryRouter initialEntries={["/admin/inventory"]}>
      <Routes>
        <Route path="/admin/inventory" element={<AdminInventoryScreen />} />
        <Route path="/" element={<div>Home screen</div>} />
      </Routes>
    </MemoryRouter>
  );

  expect(await screen.findByText("Home screen")).toBeInTheDocument();
  expect(sessionStorage.getItem("coinnect_admin_token")).toBeNull();
});
