import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import AdminLoginScreen from "./AdminLoginScreen";


test("successful PIN login stores token and opens inventory page", async () => {
  const user = userEvent.setup();
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: true,
    json: async () => ({
      token: "admin-token",
      session_id: "session-1",
      expires_at: "2026-01-01T12:15:00",
    }),
  });

  render(
    <MemoryRouter initialEntries={["/admin/login"]}>
      <Routes>
        <Route path="/admin/login" element={<AdminLoginScreen />} />
        <Route path="/admin/inventory" element={<div>Inventory page</div>} />
      </Routes>
    </MemoryRouter>
  );

  for (const digit of ["2", "4", "6", "8"]) {
    await user.click(screen.getByRole("button", { name: digit }));
  }
  await user.click(screen.getByRole("button", { name: "Enter maintenance" }));

  expect(await screen.findByText("Inventory page")).toBeInTheDocument();
  expect(sessionStorage.getItem("coinnect_admin_token")).toBe("admin-token");
});


test("failed PIN login shows backend error", async () => {
  const user = userEvent.setup();
  vi.spyOn(globalThis, "fetch").mockResolvedValue({
    ok: false,
    json: async () => ({ detail: "Invalid admin PIN" }),
  });

  render(
    <MemoryRouter>
      <AdminLoginScreen />
    </MemoryRouter>
  );

  await user.click(screen.getByRole("button", { name: "2" }));
  await user.click(screen.getByRole("button", { name: "4" }));
  await user.click(screen.getByRole("button", { name: "6" }));
  await user.click(screen.getByRole("button", { name: "8" }));
  await user.click(screen.getByRole("button", { name: "Enter maintenance" }));

  expect(await screen.findByText("Invalid admin PIN")).toBeInTheDocument();
});
