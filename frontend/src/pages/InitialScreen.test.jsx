import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import InitialScreen from "./InitialScreen";


test("holding the home logo for five seconds opens admin login", () => {
  vi.useFakeTimers();
  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<InitialScreen />} />
        <Route path="/admin/login" element={<div>Admin login</div>} />
      </Routes>
    </MemoryRouter>
  );

  fireEvent.pointerDown(screen.getByAltText("Coinnect"));
  act(() => vi.advanceTimersByTime(5000));

  expect(screen.getByText("Admin login")).toBeInTheDocument();
  vi.useRealTimers();
});
