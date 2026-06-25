import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import AdminInventoryScreen from "./AdminInventoryScreen";


const inventory = {
  bill_dispenser_counts: {
    PHP_20: 1, PHP_50: 2, PHP_100: 3, PHP_200: 4, PHP_500: 5,
    PHP_1000: 6, USD_10: 7, USD_50: 8, USD_100: 9,
    EUR_5: 10, EUR_10: 11, EUR_20: 12,
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
