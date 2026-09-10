import { act, render, screen } from "@testing-library/react";
import DeadlineCountdown from "./DeadlineCountdown";
import InactivityWarningModal from "../transaction/InactivityWarningModal";

const epoch = Date.parse("2026-09-07T12:00:00Z");
const stamp = seconds => new Date(epoch + seconds * 1000).toISOString();
const props = { deadline: stamp(90), serverTime: stamp(0), durationSeconds: 90 };
beforeEach(() => { vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date", "performance"] }); vi.setSystemTime(epoch); });
afterEach(() => { vi.useRealTimers(); });

test("ticks from server time despite a skewed wall clock and repeated snapshots", () => {
  vi.setSystemTime(epoch + 86400000);
  const view = render(<DeadlineCountdown {...props} />);
  expect(screen.getByRole("timer")).toHaveTextContent("90s");
  act(() => vi.advanceTimersByTime(30000));
  view.rerender(<DeadlineCountdown {...props} />);
  expect(screen.getByRole("timer")).toHaveTextContent("60s");
  expect(Number(screen.getByRole("progressbar").getAttribute("aria-valuenow"))).toBeCloseTo(66.67, 1);
  vi.setSystemTime(epoch - 86400000);
  act(() => vi.advanceTimersByTime(1000));
  expect(screen.getByRole("timer")).toHaveTextContent("59s");
});

test("only new deadlines extend the display, including after a reload", () => {
  const view = render(<DeadlineCountdown {...props} />);
  act(() => vi.advanceTimersByTime(30000));
  view.rerender(<DeadlineCountdown {...props} serverTime={stamp(30)} deadline={stamp(120)} />);
  expect(screen.getByRole("timer")).toHaveTextContent("90s");
  view.unmount();
  expect(vi.getTimerCount()).toBe(0);
  render(<DeadlineCountdown {...props} serverTime={stamp(60)} deadline={stamp(120)} />);
  expect(screen.getByRole("timer")).toHaveTextContent("60s");
  expect(Number(screen.getByRole("progressbar").getAttribute("aria-valuenow"))).toBeCloseTo(66.67, 1);
});

test("expiry clamps to zero and waits for backend status", () => {
  render(<DeadlineCountdown {...props} />);
  act(() => vi.advanceTimersByTime(100000));
  expect(screen.getByRole("timer")).toHaveTextContent("0s");
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0");
  expect(screen.getByText("Checking transaction status…")).toBeInTheDocument();
});

test.each([{ deadline: null }, { deadline: "bad" }, { durationSeconds: undefined }, { durationSeconds: 0 }])("invalid timing renders a checking state: %j", invalid => {
  render(<DeadlineCountdown {...props} {...invalid} />);
  expect(screen.queryByRole("timer")).not.toBeInTheDocument();
  expect(screen.getByText("Checking session…")).toBeInTheDocument();
});

test("processing hides the intake clock and progress never exceeds 100", () => {
  const view = render(<DeadlineCountdown {...props} deadline={stamp(200)} />);
  expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
  view.rerender(<DeadlineCountdown {...props} active={false} />);
  expect(screen.queryByRole("timer")).not.toBeInTheDocument();
  expect(screen.getByText("Processing your transaction…")).toBeInTheDocument();
});

test("warning and inline timer agree on expiry", () => {
  render(<><DeadlineCountdown {...props} /><InactivityWarningModal expiresAt={stamp(90)} warningAt={stamp(60)} serverTime={stamp(0)} /></>);
  act(() => vi.advanceTimersByTime(60000));
  expect(screen.getByText("Are you still there?")).toBeInTheDocument();
  expect(screen.getAllByText("30s")).toHaveLength(2);
});
