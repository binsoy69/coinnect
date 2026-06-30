import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ExternalLink,
  Loader2,
  QrCode,
  RefreshCw,
  WalletCards,
  XCircle,
} from 'lucide-react';
import {
  cancelEWalletSandboxSession,
  createEWalletSandboxSession,
  fetchEWalletSandboxConfig,
  fetchEWalletSandboxSession,
  fetchEWalletSandboxSessions,
} from './api';

const FLOWS = [
  { provider: 'gcash', direction: 'cash-in', label: 'GCash Cash In' },
  { provider: 'gcash', direction: 'cash-out', label: 'GCash Cash Out' },
  { provider: 'maya', direction: 'cash-in', label: 'Maya Cash In' },
  { provider: 'maya', direction: 'cash-out', label: 'Maya Cash Out' },
];

const STATE_PRESENTATION = {
  PENDING_CALLBACK: {
    label: 'Waiting for callback',
    className: 'bg-amber-50 text-amber-800',
    icon: Clock3,
  },
  VERIFIED: {
    label: 'Verified',
    className: 'bg-emerald-50 text-emerald-700',
    icon: CheckCircle2,
  },
  FAILED: {
    label: 'Failed',
    className: 'bg-red-50 text-red-700',
    icon: XCircle,
  },
  TIMED_OUT: {
    label: 'Timed out',
    className: 'bg-red-50 text-red-700',
    icon: Clock3,
  },
  CANCELLED: {
    label: 'Cancelled',
    className: 'bg-gray-100 text-gray-700',
    icon: XCircle,
  },
};

export default function EWalletSandboxPanel({ token }) {
  const [config, setConfig] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [selectedFlow, setSelectedFlow] = useState(null);
  const [amount, setAmount] = useState('100');
  const [mobileNumber, setMobileNumber] = useState('');
  const [accountName, setAccountName] = useState('');
  const [activeSession, setActiveSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [configData, sessionData] = await Promise.all([
        fetchEWalletSandboxConfig(token),
        fetchEWalletSandboxSessions(token),
      ]);
      setConfig(configData);
      setSessions(sessionData);
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    const timer = window.setTimeout(load, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  useEffect(() => {
    if (
      !activeSession ||
      activeSession.state !== 'PENDING_CALLBACK'
    ) {
      return undefined;
    }
    const interval = window.setInterval(async () => {
      try {
        const refreshed = await fetchEWalletSandboxSession(
          token,
          activeSession.transaction_id,
        );
        setActiveSession(refreshed);
        setSessions((current) => upsertSession(current, refreshed));
      } catch (err) {
        setError(err.message);
      }
    }, 2000);
    return () => window.clearInterval(interval);
  }, [activeSession, token]);

  const formValid = useMemo(() => {
    const numericAmount = Number(amount);
    if (
      !selectedFlow ||
      !Number.isInteger(numericAmount) ||
      numericAmount < 1 ||
      numericAmount > 50000
    ) {
      return false;
    }
    if (selectedFlow.direction === 'cash-in') {
      return /^09\d{9}$/.test(mobileNumber) && accountName.trim().length >= 2;
    }
    return true;
  }, [accountName, amount, mobileNumber, selectedFlow]);

  async function handleCreate(event) {
    event.preventDefault();
    if (!formValid) return;
    setSubmitting(true);
    setError('');
    const payload = {
      provider: selectedFlow.provider,
      direction: selectedFlow.direction,
      amount: Number(amount),
    };
    if (selectedFlow.direction === 'cash-in') {
      payload.mobile_number = mobileNumber;
      payload.account_name = accountName.trim();
    }
    try {
      const session = await createEWalletSandboxSession(token, payload);
      setActiveSession(session);
      setSessions((current) => upsertSession(current, session));
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancel() {
    if (!activeSession) return;
    setSubmitting(true);
    setError('');
    try {
      const session = await cancelEWalletSandboxSession(
        token,
        activeSession.transaction_id,
      );
      setActiveSession(session);
      setSessions((current) => upsertSession(current, session));
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  const ready = Boolean(config?.ready);

  return (
    <section className="rounded-card bg-white p-6 shadow-sm">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-50 text-sky-700">
            <WalletCards className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-black uppercase tracking-[0.16em] text-sky-700">
              Gateway diagnostics
            </p>
            <h2 className={`text-2xl font-extrabold tracking-tight ${config?.sandbox === false ? 'text-red-600' : ''}`}>
              {config?.sandbox === false ? 'PayMongo Live Gateway' : 'PayMongo Sandbox'}
            </h2>
            <p className="mt-1 max-w-3xl text-sm font-medium text-gray-500">
              {config?.sandbox === false ? (
                <>
                  Tests live production QR Ph and wallet transfers. <strong className="text-red-600 font-extrabold">Real money will be moved.</strong> No physical cash is accepted or dispensed.
                </>
              ) : (
                'Tests live sandbox QR Ph and wallet transfers without accepting or dispensing physical cash.'
              )}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="flex h-11 items-center gap-2 rounded-button border-2 border-gray-200 px-4 font-bold text-gray-700"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {error && (
        <div className="mb-5 flex items-center gap-3 rounded-2xl bg-red-50 px-4 py-3 font-semibold text-red-700">
          <AlertTriangle className="h-5 w-5 shrink-0" />
          {error}
        </div>
      )}

      {!loading && config && config.sandbox === false && (
        <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 p-5">
          <div className="flex items-center gap-2 font-extrabold text-red-950">
            <AlertTriangle className="h-5 w-5 text-red-700" />
            WARNING: Live Gateway Active
          </div>
          <p className="mt-2 text-sm text-red-900 font-semibold">
            This panel is currently running in LIVE mode using production credentials. Any actions performed here will result in real financial transactions (actual InstaPay transfers and QR Ph charges). The physical kiosk will NOT accept or dispense cash during this diagnostic run.
          </p>
        </div>
      )}

      {!loading && !ready && (
        <div className="mb-6 rounded-2xl border border-amber-200 bg-amber-50 p-5">
          <div className="flex items-center gap-2 font-extrabold text-amber-900">
            <AlertTriangle className="h-5 w-5" />
            Not configured
          </div>
          <p className="mt-2 text-sm text-amber-800">
            Configure every item below before creating a sandbox session.
          </p>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm font-semibold text-amber-900">
            {(config?.missing || []).map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {config && (
        <div className="mb-6 grid gap-3 lg:grid-cols-2">
          <CallbackUrl
            label="Payment webhook"
            value={config.payment_callback_url}
          />
          <CallbackUrl
            label="Transfer callback"
            value={config.transfer_callback_url}
          />
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <div>
          <div className="grid gap-3 sm:grid-cols-2">
            {FLOWS.map((flow) => {
              const selected =
                selectedFlow?.provider === flow.provider &&
                selectedFlow?.direction === flow.direction;
              return (
                <button
                  key={`${flow.provider}-${flow.direction}`}
                  type="button"
                  aria-label={flow.label}
                  disabled={!ready}
                  onClick={() => {
                    setSelectedFlow(flow);
                    setActiveSession(null);
                    setError('');
                  }}
                  className={`rounded-2xl border-2 p-4 text-left transition ${
                    selected
                      ? 'border-sky-600 bg-sky-50 text-sky-900'
                      : 'border-gray-200 hover:border-sky-300'
                  } disabled:cursor-not-allowed disabled:opacity-45`}
                >
                  <span className="block text-lg font-extrabold">
                    {flow.label}
                  </span>
                  <span className="mt-1 block text-sm text-gray-500">
                    {flow.direction === 'cash-in'
                      ? (config?.sandbox === false ? 'Send a live wallet transfer' : 'Send a sandbox wallet transfer')
                      : (config?.sandbox === false ? 'Create and verify a live QR Ph payment' : 'Create and verify a sandbox QR Ph payment')}
                  </span>
                </button>
              );
            })}
          </div>

          {selectedFlow && (
            <form onSubmit={handleCreate} className="mt-5 space-y-4">
              <label className="block">
                <span className="mb-1 block text-sm font-bold text-gray-700">
                  Amount in PHP
                </span>
                <input
                  aria-label="Amount in PHP"
                  type="number"
                  min="1"
                  max="50000"
                  step="1"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  className="h-12 w-full rounded-xl border-2 border-gray-200 px-4 outline-none focus:border-sky-600"
                />
              </label>
              {selectedFlow.direction === 'cash-in' && (
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="block">
                    <span className="mb-1 block text-sm font-bold text-gray-700">
                      Mobile number
                    </span>
                    <input
                      aria-label="Mobile number"
                      value={mobileNumber}
                      onChange={(event) => setMobileNumber(event.target.value)}
                      placeholder="09XXXXXXXXX"
                      className="h-12 w-full rounded-xl border-2 border-gray-200 px-4 outline-none focus:border-sky-600"
                    />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-sm font-bold text-gray-700">
                      Account name
                    </span>
                    <input
                      aria-label="Account name"
                      value={accountName}
                      onChange={(event) => setAccountName(event.target.value)}
                      className="h-12 w-full rounded-xl border-2 border-gray-200 px-4 outline-none focus:border-sky-600"
                    />
                  </label>
                </div>
              )}
              <button
                type="submit"
                disabled={!formValid || submitting}
                className={`flex h-12 w-full items-center justify-center gap-2 rounded-button px-5 font-extrabold text-white disabled:cursor-not-allowed disabled:opacity-45 ${config?.sandbox === false ? 'bg-red-600 hover:bg-red-700' : 'bg-sky-700 hover:bg-sky-800'}`}
              >
                {submitting && <Loader2 className="h-5 w-5 animate-spin" />}
                {config?.sandbox === false ? 'Start live test (moves real money)' : 'Start sandbox test'}
              </button>
            </form>
          )}
        </div>

        <SessionDetail
          session={activeSession}
          submitting={submitting}
          onCancel={handleCancel}
          config={config}
        />
      </div>

      <div className="mt-7 border-t border-gray-200 pt-5">
        <h3 className="mb-3 text-lg font-extrabold">{config?.sandbox === false ? 'Live' : 'Sandbox'} session history</h3>
        {sessions.length === 0 ? (
          <p className="rounded-2xl bg-gray-50 p-4 text-sm font-semibold text-gray-500">
            No e-wallet {config?.sandbox === false ? 'live' : 'sandbox'} sessions yet.
          </p>
        ) : (
          <div className="grid gap-2">
            {sessions.map((session) => (
              <button
                type="button"
                key={session.transaction_id}
                onClick={() => setActiveSession(session)}
                className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-gray-50 px-4 py-3 text-left hover:bg-gray-100"
              >
                <span>
                  <strong className="capitalize">{session.provider}</strong>{' '}
                  {session.direction} - PHP {session.amount}
                </span>
                <SessionState state={session.state} />
              </button>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function CallbackUrl({ label, value }) {
  return (
    <div className="rounded-2xl bg-gray-50 p-3">
      <p className="text-xs font-black uppercase tracking-wide text-gray-500">
        {label}
      </p>
      <p className="mt-1 break-all text-xs font-semibold text-gray-800">
        {value || 'Unavailable'}
      </p>
    </div>
  );
}

function SessionDetail({ session, submitting, onCancel, config }) {
  if (!session) {
    return (
      <div className="flex min-h-[300px] items-center justify-center rounded-2xl border-2 border-dashed border-gray-200 p-6 text-center text-sm font-semibold text-gray-500">
        Select a flow and start a test to view gateway details.
      </div>
    );
  }
  return (
    <div className="rounded-2xl bg-gray-950 p-5 text-white">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-black uppercase tracking-wider text-white/50">
            Active session
          </p>
          <p className="mt-1 font-extrabold capitalize">
            {session.provider} {session.direction}
          </p>
        </div>
        <SessionState state={session.state} />
      </div>

      {session.qr_image_url && (
        <div className="mb-4 rounded-2xl bg-white p-4 text-center text-gray-950">
          <QrCode className="mx-auto mb-2 h-5 w-5 text-sky-700" />
          <img
            src={session.qr_image_url}
            alt="PayMongo QR Ph"
            className="mx-auto max-h-64 max-w-full"
          />
          {session.test_url && (
            <a
              href={session.test_url}
              target="_blank"
              rel="noreferrer"
              className={`mt-3 inline-flex items-center gap-2 font-bold ${config?.sandbox === false ? 'text-red-600 hover:text-red-700' : 'text-sky-700 hover:text-sky-800'}`}
            >
              {config?.sandbox === false ? 'Open live payment' : 'Open sandbox payment'}
              <ExternalLink className="h-4 w-4" />
            </a>
          )}
        </div>
      )}

      <DetailRow label="Amount" value={`PHP ${session.amount}`} />
      <DetailRow
        label="Payment Intent"
        value={session.gateway_payment_intent_id}
      />
      <DetailRow
        label="Batch Transfer"
        value={session.gateway_batch_transfer_id}
      />
      <DetailRow label="Transfer" value={session.gateway_transfer_id} />
      <DetailRow label="Gateway status" value={session.gateway_status} />

      {session.error_message && (
        <div className="mt-4 rounded-xl bg-red-950/70 p-3 text-sm text-red-100">
          <strong>{session.error_code}</strong>
          <p className="mt-1">{session.error_message}</p>
        </div>
      )}

      {session.state === 'PENDING_CALLBACK' && (
        <button
          type="button"
          disabled={submitting}
          onClick={onCancel}
          className="mt-5 h-11 w-full rounded-button bg-white/10 px-4 font-bold text-white hover:bg-white/20 disabled:opacity-50"
        >
          Cancel local test
        </button>
      )}
      {session.state === 'CANCELLED' && (
        <p className="mt-4 text-xs leading-5 text-white/60">
          Cancelling local tracking does not cancel the PayMongo resource.
        </p>
      )}
    </div>
  );
}

function SessionState({ state }) {
  const config = STATE_PRESENTATION[state] || {
    label: state,
    className: 'bg-gray-100 text-gray-700',
    icon: Clock3,
  };
  const Icon = config.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-extrabold ${config.className}`}
    >
      <Icon className="h-4 w-4" />
      {config.label}
    </span>
  );
}

function DetailRow({ label, value }) {
  if (!value) return null;
  return (
    <div className="flex items-start justify-between gap-4 border-b border-white/10 py-2 text-sm">
      <span className="text-white/50">{label}</span>
      <span className="break-all text-right font-bold">{value}</span>
    </div>
  );
}

function upsertSession(sessions, session) {
  return [
    session,
    ...sessions.filter(
      (item) => item.transaction_id !== session.transaction_id,
    ),
  ].slice(0, 100);
}
