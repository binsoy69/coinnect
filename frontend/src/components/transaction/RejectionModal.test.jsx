import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import RejectionModal from "./RejectionModal";

describe("RejectionModal", () => {
  it("renders null when isOpen is false", () => {
    const { container } = render(
      <RejectionModal
        isOpen={false}
        error="UNEXPECTED_DENOMINATION"
        onClose={vi.fn()}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders unrecognized bill message and buttons correctly", () => {
    const handleClose = vi.fn();
    const handleChangeSelection = vi.fn();

    render(
      <RejectionModal
        isOpen={true}
        error="UNEXPECTED_DENOMINATION"
        onClose={handleClose}
        onChangeSelection={handleChangeSelection}
      />
    );

    expect(screen.getByText("Unrecognized Bill")).toBeInTheDocument();
    expect(
      screen.getByText(
        "The inserted bill denomination or currency is not accepted for this transaction."
      )
    ).toBeInTheDocument();

    const okButton = screen.getByRole("button", { name: /OK, Try Again/i });
    expect(okButton).toBeInTheDocument();
    fireEvent.click(okButton);
    expect(handleClose).toHaveBeenCalledTimes(1);

    const changeButton = screen.getByRole("button", {
      name: /Choose Different Bill/i,
    });
    expect(changeButton).toBeInTheDocument();
    fireEvent.click(changeButton);
    expect(handleChangeSelection).toHaveBeenCalledTimes(1);
  });

  it("handles critical error appropriately", () => {
    const handleNavigateWarning = vi.fn();

    render(
      <RejectionModal
        isOpen={true}
        error="JAM"
        onClose={vi.fn()}
        onNavigateWarning={handleNavigateWarning}
      />
    );

    expect(screen.getByText("Hardware Jam Detected")).toBeInTheDocument();
    const actionBtn = screen.getByRole("button", {
      name: /Go to Warning \/ Help/i,
    });
    expect(actionBtn).toBeInTheDocument();
    fireEvent.click(actionBtn);
    expect(handleNavigateWarning).toHaveBeenCalledTimes(1);
  });
});
