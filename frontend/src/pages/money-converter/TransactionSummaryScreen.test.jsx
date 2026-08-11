import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import TransactionSummaryScreen from "./TransactionSummaryScreen";


vi.mock("../../context/TransactionContext", () => ({
  useTransaction: () => ({
    transaction: {
      moneyInserted: 25,
      totalDue: 23,
      selectedDispenseDenominations: [20],
    },
    getServiceConfig: () => ({
      name: "Coins to Bills",
      shortName: "Coins to Bills",
      icon: "/coin.svg",
    }),
    getMoneyToDispense: () => 22,
  }),
}));

test("shows total output and excess coin refund before confirmation", () => {
  render(
    <MemoryRouter
      initialEntries={["/money-converter/coin-to-bill/summary"]}
    >
      <Routes>
        <Route
          path="/money-converter/:type/summary"
          element={<TransactionSummaryScreen />}
        />
      </Routes>
    </MemoryRouter>,
  );

  expect(screen.getByText("Money to Dispense").nextSibling).toHaveTextContent(
    "P22",
  );
  expect(screen.getByText("Excess Coin Refund").nextSibling).toHaveTextContent(
    "P2",
  );
});
