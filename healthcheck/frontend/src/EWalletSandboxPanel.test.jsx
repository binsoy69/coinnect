import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import EWalletSandboxPanel from './EWalletSandboxPanel';
import {
  cancelEWalletSandboxSession,
  createEWalletSandboxSession,
  fetchEWalletSandboxConfig,
  fetchEWalletSandboxSession,
  fetchEWalletSandboxSessions,
} from './api';

vi.mock('./api', () => ({
  cancelEWalletSandboxSession: vi.fn(),
  createEWalletSandboxSession: vi.fn(),
  fetchEWalletSandboxConfig: vi.fn(),
  fetchEWalletSandboxSession: vi.fn(),
  fetchEWalletSandboxSessions: vi.fn(),
}));

const readyConfig = {
  ready: true,
  sandbox: true,
  missing: [],
  payment_callback_url:
    'https://healthcheck.example/api/v1/ewallet-sandbox/callbacks/payment',
  transfer_callback_url:
    'https://healthcheck.example/api/v1/ewallet-sandbox/callbacks/transfer',
  timeout_seconds: 600,
};

const pendingCashOut = {
  transaction_id: 'session-1',
  provider: 'gcash',
  direction: 'cash-out',
  amount: 100,
  state: 'PENDING_CALLBACK',
  gateway_status: 'awaiting_next_action',
  gateway_payment_intent_id: 'pi_1',
  qr_image_url: 'https://sandbox.example/qr.png',
  test_url: 'https://sandbox.example/pay',
};

beforeEach(() => {
  vi.clearAllMocks();
  fetchEWalletSandboxConfig.mockResolvedValue(readyConfig);
  fetchEWalletSandboxSessions.mockResolvedValue([]);
});

afterEach(() => {
  vi.useRealTimers();
});

describe('EWalletSandboxPanel', () => {
  test('shows configuration blockers without enabling session creation', async () => {
    fetchEWalletSandboxConfig.mockResolvedValue({
      ...readyConfig,
      ready: false,
      missing: ['PAYMONGO_WEBHOOK_SECRET'],
    });

    render(<EWalletSandboxPanel token="token" />);

    expect(await screen.findByText('Not configured')).toBeInTheDocument();
    expect(screen.getByText('PAYMONGO_WEBHOOK_SECRET')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'GCash Cash Out' }),
    ).toBeDisabled();
  });

  test('offers four branded flows and cash-in identity fields', async () => {
    const user = userEvent.setup();
    render(<EWalletSandboxPanel token="token" />);

    expect(
      await screen.findByRole('button', { name: 'GCash Cash In' }),
    ).toBeEnabled();
    expect(
      screen.getByRole('button', { name: 'GCash Cash Out' }),
    ).toBeEnabled();
    expect(
      screen.getByRole('button', { name: 'Maya Cash In' }),
    ).toBeEnabled();
    expect(
      screen.getByRole('button', { name: 'Maya Cash Out' }),
    ).toBeEnabled();

    await user.click(screen.getByRole('button', { name: 'Maya Cash In' }));

    expect(screen.getByLabelText('Mobile number')).toBeInTheDocument();
    expect(screen.getByLabelText('Account name')).toBeInTheDocument();
  });

  test('creates a direct-amount cash-in session', async () => {
    const user = userEvent.setup();
    createEWalletSandboxSession.mockResolvedValue({
      transaction_id: 'cash-in-1',
      provider: 'maya',
      direction: 'cash-in',
      amount: 250,
      state: 'PENDING_CALLBACK',
      gateway_batch_transfer_id: 'batch_1',
      gateway_transfer_id: 'transfer_1',
    });
    render(<EWalletSandboxPanel token="token" />);
    await screen.findByText('PayMongo Sandbox');

    await user.click(screen.getByRole('button', { name: 'Maya Cash In' }));
    await user.clear(screen.getByLabelText('Amount in PHP'));
    await user.type(screen.getByLabelText('Amount in PHP'), '250');
    await user.type(screen.getByLabelText('Mobile number'), '09181234567');
    await user.type(screen.getByLabelText('Account name'), 'Sandbox User');
    await user.click(screen.getByRole('button', { name: 'Start sandbox test' }));

    expect(createEWalletSandboxSession).toHaveBeenCalledWith('token', {
      provider: 'maya',
      direction: 'cash-in',
      amount: 250,
      mobile_number: '09181234567',
      account_name: 'Sandbox User',
    });
    expect(await screen.findByText('batch_1')).toBeInTheDocument();
    expect(screen.getByText('transfer_1')).toBeInTheDocument();
  });

  test('renders QR details and polls pending sessions to a terminal state', async () => {
    createEWalletSandboxSession.mockResolvedValue(pendingCashOut);
    fetchEWalletSandboxSession.mockResolvedValue({
      ...pendingCashOut,
      state: 'VERIFIED',
      gateway_status: 'paid',
    });
    const user = userEvent.setup();
    render(<EWalletSandboxPanel token="token" />);
    await screen.findByText('PayMongo Sandbox');

    await user.click(screen.getByRole('button', { name: 'GCash Cash Out' }));
    await user.clear(screen.getByLabelText('Amount in PHP'));
    await user.type(screen.getByLabelText('Amount in PHP'), '100');
    await user.click(screen.getByRole('button', { name: 'Start sandbox test' }));

    expect(await screen.findByAltText('PayMongo QR Ph')).toHaveAttribute(
      'src',
      pendingCashOut.qr_image_url,
    );
    expect(screen.getByRole('link', { name: 'Open sandbox payment' })).toHaveAttribute(
      'href',
      pendingCashOut.test_url,
    );

    await waitFor(() => {
      expect(fetchEWalletSandboxSession).toHaveBeenCalledWith(
        'token',
        'session-1',
      );
      expect(screen.getAllByText('Verified').length).toBeGreaterThan(0);
    }, { timeout: 3500 });
  }, 5000);

  test('cancels local tracking and explains gateway behavior', async () => {
    const user = userEvent.setup();
    createEWalletSandboxSession.mockResolvedValue(pendingCashOut);
    cancelEWalletSandboxSession.mockResolvedValue({
      ...pendingCashOut,
      state: 'CANCELLED',
    });
    render(<EWalletSandboxPanel token="token" />);
    await screen.findByText('PayMongo Sandbox');

    await user.click(screen.getByRole('button', { name: 'GCash Cash Out' }));
    await user.click(screen.getByRole('button', { name: 'Start sandbox test' }));
    await user.click(screen.getByRole('button', { name: 'Cancel local test' }));

    expect(cancelEWalletSandboxSession).toHaveBeenCalledWith(
      'token',
      'session-1',
    );
    await waitFor(() => {
      expect(screen.getAllByText('Cancelled').length).toBeGreaterThan(0);
    });
    expect(
      screen.getByText(/does not cancel the PayMongo resource/i),
    ).toBeInTheDocument();
  });
});
