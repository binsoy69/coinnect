import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  CircleDot,
  Cpu,
  KeyRound,
  Loader2,
  LockKeyhole,
  LogOut,
  Play,
  Printer,
  Radio,
  RefreshCw,
  Server,
  ShieldCheck,
  Wrench,
  XCircle,
  Zap,
} from 'lucide-react';
import {
  TOKEN_KEY,
  fetchComponents,
  fetchRecentRuns,
  fetchStatus,
  login,
  runTest,
  API_BASE,
} from './api';
import EWalletSandboxPanel from './EWalletSandboxPanel';

const KIND_ICONS = {
  connectivity: Radio,
  sensor: Cpu,
  actuator: Zap,
  camera: Camera,
  status: LockKeyhole,
  printer: Printer,
  ml: Cpu,
};

function App() {
  const [token, setToken] = useState(
    () => localStorage.getItem(TOKEN_KEY) || '',
  );
  const [pin, setPin] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loadingLogin, setLoadingLogin] = useState(false);
  const [groups, setGroups] = useState([]);
  const [status, setStatus] = useState(null);
  const [runs, setRuns] = useState([]);
  const [runningId, setRunningId] = useState('');
  const [selectedResult, setSelectedResult] = useState(null);
  const [error, setError] = useState('');

  const authenticated = Boolean(token);

  const loadDashboard = useCallback(async () => {
    if (!token) return;
    try {
      const [componentData, statusData, runData] = await Promise.all([
        fetchComponents(token),
        fetchStatus(token),
        fetchRecentRuns(token),
      ]);
      setGroups(componentData);
      setStatus(statusData);
      setRuns(runData);
      setError('');
    } catch (err) {
      setError(err.message);
      if (err.message.toLowerCase().includes('token')) {
        localStorage.removeItem(TOKEN_KEY);
        setToken('');
      }
    }
  }, [token]);

  useEffect(() => {
    if (!authenticated) return undefined;
    const timer = window.setTimeout(() => {
      loadDashboard();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [authenticated, loadDashboard]);

  useEffect(() => {
    if (!authenticated) return undefined;
    const timer = window.setInterval(() => {
      fetchStatus(token)
        .then(setStatus)
        .catch((err) => setError(err.message));
    }, 3000);
    return () => window.clearInterval(timer);
  }, [authenticated, token]);

  async function handleLogin(event) {
    event.preventDefault();
    setLoadingLogin(true);
    setLoginError('');
    try {
      const data = await login(pin);
      localStorage.setItem(TOKEN_KEY, data.token);
      setToken(data.token);
      setPin('');
    } catch (err) {
      setLoginError(err.message);
    } finally {
      setLoadingLogin(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken('');
    setGroups([]);
    setStatus(null);
    setRuns([]);
    setSelectedResult(null);
  }

  async function handleRun(test) {
    setRunningId(test.id);
    setError('');
    try {
      const result = await runTest(token, test.id);
      setRuns((current) => [result, ...current].slice(0, 100));
      setSelectedResult(result);
      setStatus(await fetchStatus(token));
    } catch (err) {
      setError(err.message);
    } finally {
      setRunningId('');
    }
  }

  if (!authenticated) {
    return (
      <LoginScreen
        pin={pin}
        setPin={setPin}
        onSubmit={handleLogin}
        loading={loadingLogin}
        error={loginError}
      />
    );
  }

  return (
    <Dashboard
      token={token}
      groups={groups}
      status={status}
      runs={runs}
      runningId={runningId}
      selectedResult={selectedResult}
      error={error}
      onRun={handleRun}
      onRefresh={loadDashboard}
      onLogout={handleLogout}
      onSelectResult={setSelectedResult}
    />
  );
}

function LoginScreen({ pin, setPin, onSubmit, loading, error }) {
  return (
    <main className="min-h-screen bg-gradient-to-br from-coinnect-navy to-coinnect-navy-soft text-white">
      <section className="mx-auto flex min-h-screen max-w-5xl items-center px-8">
        <div className="grid w-full gap-12 lg:grid-cols-[1fr_420px] lg:items-center">
          <div>
            <div className="mb-8 flex h-20 w-20 items-center justify-center rounded-[24px] bg-coinnect-primary shadow-panel">
              <Wrench className="h-10 w-10" />
            </div>
            <p className="mb-3 text-lg font-medium text-white/70">
              Coinnect Maintenance
            </p>
            <h1 className="max-w-2xl text-5xl font-extrabold leading-tight tracking-tight">
              System Health Check
            </h1>
            <div className="mt-8 grid max-w-xl gap-3 text-base text-white/70">
              <StatusLine icon={Server} text="Main kiosk backend stopped" />
              <StatusLine icon={ShieldCheck} text="PIN protected access" />
              <StatusLine icon={Zap} text="One-shot hardware tests" />
            </div>
          </div>

          <motion.form
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            onSubmit={onSubmit}
            className="rounded-card bg-white p-8 text-gray-950 shadow-panel"
          >
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-coinnect-primary/10 text-coinnect-primary">
                <KeyRound className="h-6 w-6" />
              </div>
              <div>
                <h2 className="text-2xl font-extrabold tracking-tight">
                  Technician PIN
                </h2>
                <p className="text-sm text-gray-500">Authorized access only</p>
              </div>
            </div>

            <input
              value={pin}
              onChange={(event) => setPin(event.target.value)}
              type="password"
              inputMode="numeric"
              autoFocus
              className="mb-4 h-16 w-full rounded-2xl border-2 border-gray-200 px-5 text-2xl font-bold tracking-[0.35em] outline-none transition focus:border-coinnect-primary"
            />

            {error && (
              <div className="mb-4 flex items-center gap-2 rounded-2xl bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
                <XCircle className="h-5 w-5" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !pin}
              className="flex h-16 w-full items-center justify-center gap-3 rounded-button bg-coinnect-primary px-8 text-lg font-extrabold text-white transition hover:bg-coinnect-primary-dark disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-6 w-6 animate-spin" /> : null}
              Unlock Diagnostics
            </button>
          </motion.form>
        </div>
      </section>
    </main>
  );
}

function Dashboard({
  token,
  groups,
  status,
  runs,
  runningId,
  selectedResult,
  error,
  onRun,
  onRefresh,
  onLogout,
  onSelectResult,
}) {
  const latestByTest = useMemo(() => {
    const latest = new Map();
    for (const run of runs) {
      if (!latest.has(run.test_id)) {
        latest.set(run.test_id, run);
      }
    }
    return latest;
  }, [runs]);

  const testCount = groups.reduce((total, group) => total + group.tests.length, 0);

  return (
    <main className="min-h-screen bg-surface-light text-gray-950">
      <header className="bg-gradient-to-br from-coinnect-navy to-coinnect-navy-soft text-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-5 px-8 py-6">
          <div className="flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-[18px] bg-coinnect-primary">
              <Wrench className="h-8 w-8" />
            </div>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-white/60">
                Coinnect
              </p>
              <h1 className="text-3xl font-extrabold tracking-tight">
                Health Check
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={onRefresh}
              className="flex h-12 items-center gap-2 rounded-button bg-white/10 px-5 font-bold text-white transition hover:bg-white/20"
            >
              <RefreshCw className="h-5 w-5" />
              Refresh
            </button>
            <button
              type="button"
              onClick={onLogout}
              className="flex h-12 items-center gap-2 rounded-button bg-white px-5 font-bold text-coinnect-navy transition hover:bg-gray-100"
            >
              <LogOut className="h-5 w-5" />
              Lock
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-6 px-8 py-6 xl:grid-cols-[1fr_360px]">
        <section className="space-y-6">
          <StatusOverview status={status} testCount={testCount} />
          <EWalletSandboxPanel token={token} />

          {error && (
            <div className="flex items-center gap-3 rounded-card bg-red-50 px-5 py-4 font-semibold text-red-700">
              <AlertTriangle className="h-6 w-6" />
              {error}
            </div>
          )}

          {groups.map((group) => (
            <ComponentSection
              key={group.id}
              group={group}
              latestByTest={latestByTest}
              runningId={runningId}
              busy={Boolean(runningId || status?.busy)}
              onRun={onRun}
              onSelectResult={onSelectResult}
              token={token}
            />
          ))}
        </section>

        <aside className="space-y-6">
          <RecentRuns
            runs={runs}
            selectedResult={selectedResult}
            onSelectResult={onSelectResult}
          />
        </aside>
      </div>
    </main>
  );
}

function StatusOverview({ status, testCount }) {
  const serial = status?.serial || {};
  const billConnected = Boolean(serial.bill?.connected);
  const coinConnected = Boolean(serial.coin?.connected);

  return (
    <section className="grid gap-4 md:grid-cols-4">
      <MetricCard
        icon={Radio}
        label="Bill Controller"
        value={billConnected ? 'Connected' : 'Disconnected'}
        tone={billConnected ? 'good' : 'bad'}
      />
      <MetricCard
        icon={Radio}
        label="Coin/Security"
        value={coinConnected ? 'Connected' : 'Disconnected'}
        tone={coinConnected ? 'good' : 'bad'}
      />
      <MetricCard
        icon={Camera}
        label="Camera"
        value={status?.camera?.available ? 'Ready' : 'Unavailable'}
        tone={status?.camera?.available ? 'good' : 'bad'}
      />
      <MetricCard
        icon={CircleDot}
        label="Test Surface"
        value={`${testCount} tests`}
        tone="neutral"
      />
    </section>
  );
}

function MetricCard({ icon, label, value, tone }) {
  const IconComponent = icon;
  const tones = {
    good: 'bg-emerald-50 text-emerald-700',
    bad: 'bg-red-50 text-red-700',
    neutral: 'bg-orange-50 text-coinnect-primary',
  };

  return (
    <div className="rounded-card bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div className={`flex h-11 w-11 items-center justify-center rounded-full ${tones[tone]}`}>
          <IconComponent className="h-5 w-5" />
        </div>
      </div>
      <p className="text-sm font-semibold text-gray-500">{label}</p>
      <p className="mt-1 text-xl font-extrabold tracking-tight">{value}</p>
    </div>
  );
}

function CameraLivePreviewPanel({ token }) {
  const [streamActive, setStreamActive] = useState(false);
  const [streamSession, setStreamSession] = useState(0);

  const toggleStream = () => {
    if (streamActive) {
      setStreamActive(false);
    } else {
      setStreamSession(Date.now());
      setStreamActive(true);
    }
  };

  return (
    <div className="rounded-card bg-white p-5 shadow-sm mb-6 border border-gray-150">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-full bg-orange-50 text-coinnect-primary">
            <Camera className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-lg font-extrabold leading-tight">Camera Live Preview</h3>
            <p className="text-sm font-semibold text-gray-500">Real-time video feed from bill acceptor camera</p>
          </div>
        </div>
        <button
          type="button"
          onClick={toggleStream}
          className={`flex h-10 items-center gap-2 rounded-button px-4 font-bold text-sm transition ${
            streamActive
              ? 'bg-red-500 hover:bg-red-600 text-white shadow-sm'
              : 'bg-coinnect-primary hover:bg-coinnect-primary-dark text-white shadow-sm'
          }`}
        >
          {streamActive ? 'Stop Stream' : 'Start Stream'}
        </button>
      </div>

      <div className="relative overflow-hidden rounded-2xl bg-gray-950 flex items-center justify-center border border-gray-800" style={{ minHeight: '320px', maxHeight: '480px' }}>
        {streamActive ? (
          <img
            src={`${API_BASE}/camera/stream?token=${token}&s=${streamSession}`}
            alt="Live Stream Feed"
            className="w-full h-auto max-h-[480px] object-contain"
            onError={() => {
              setStreamActive(false);
              alert('Failed to load camera stream. Verify camera connection and try again.');
            }}
          />
        ) : (
          <div className="flex flex-col items-center justify-center text-center p-8 text-white/50">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-white/5 text-white/40">
              <Camera className="h-8 w-8" />
            </div>
            <p className="font-extrabold text-white text-base">Feed Offline</p>
            <p className="text-sm max-w-sm mt-1 text-white/45">
              Click &quot;Start Stream&quot; to connect to the active kiosk bill authentication camera.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function ComponentSection({
  group,
  latestByTest,
  runningId,
  busy,
  onRun,
  onSelectResult,
  token,
}) {
  return (
    <section>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-extrabold tracking-tight">{group.label}</h2>
          <p className="max-w-3xl text-sm font-medium text-gray-500">
            {group.description}
          </p>
        </div>
        <span className="rounded-full bg-white px-4 py-2 text-sm font-bold text-gray-600 shadow-sm">
          {group.tests.length} tests
        </span>
      </div>

      {group.id === 'rpi_bill_acceptor' && (
        <CameraLivePreviewPanel token={token} />
      )}

      <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
        {group.tests.map((test) => (
          <TestCard
            key={test.id}
            test={test}
            latest={latestByTest.get(test.id)}
            running={runningId === test.id}
            disabled={busy && runningId !== test.id}
            onRun={onRun}
            onSelectResult={onSelectResult}
          />
        ))}
      </div>
    </section>
  );
}

function TestCard({ test, latest, running, disabled, onRun, onSelectResult }) {
  const IconComponent = KIND_ICONS[test.kind] || Wrench;
  const state = latest?.status || 'idle';

  return (
    <article className="flex min-h-[210px] flex-col rounded-card bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-orange-50 text-coinnect-primary">
            <IconComponent className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h3 className="break-words text-lg font-extrabold leading-tight">
              {test.label}
            </h3>
            <p className="mt-1 text-sm font-semibold text-gray-500">
              {test.component}
            </p>
          </div>
        </div>
        <RunBadge state={running ? 'running' : state} />
      </div>

      <p className="flex-1 text-sm leading-6 text-gray-600">{test.description}</p>

      {test.caution && (
        <div className="mt-4 flex gap-2 rounded-2xl bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-800">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{test.caution}</span>
        </div>
      )}

      <div className="mt-5 flex items-center gap-3">
        <button
          type="button"
          disabled={disabled || running}
          onClick={() => onRun(test)}
          className="flex h-12 flex-1 items-center justify-center gap-2 rounded-button bg-coinnect-primary px-5 font-extrabold text-white transition hover:bg-coinnect-primary-dark disabled:cursor-not-allowed disabled:opacity-45"
        >
          {running ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <Play className="h-5 w-5" />
          )}
          Run
        </button>
        {latest && (
          <button
            type="button"
            onClick={() => onSelectResult(latest)}
            className="h-12 rounded-button border-2 border-gray-200 px-5 font-extrabold text-gray-700 transition hover:border-coinnect-primary hover:text-coinnect-primary"
          >
            Detail
          </button>
        )}
      </div>
    </article>
  );
}

function RunBadge({ state }) {
  const config = {
    passed: {
      className: 'bg-emerald-50 text-emerald-700',
      icon: CheckCircle2,
      label: 'Pass',
    },
    failed: {
      className: 'bg-red-50 text-red-700',
      icon: XCircle,
      label: 'Fail',
    },
    running: {
      className: 'bg-orange-50 text-coinnect-primary',
      icon: Loader2,
      label: 'Run',
    },
    idle: {
      className: 'bg-gray-100 text-gray-500',
      icon: CircleDot,
      label: 'Idle',
    },
  }[state];
  const Icon = config.icon;

  return (
    <span
      className={`flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-extrabold ${config.className}`}
    >
      <Icon className={`h-4 w-4 ${state === 'running' ? 'animate-spin' : ''}`} />
      {config.label}
    </span>
  );
}

function RecentRuns({ runs, selectedResult, onSelectResult }) {
  const active = selectedResult || runs[0] || null;

  return (
    <section className="rounded-card bg-white p-5 shadow-sm xl:sticky xl:top-6">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-extrabold tracking-tight">Recent Runs</h2>
        <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-bold text-gray-500">
          {runs.length}
        </span>
      </div>

      <div className="mb-5 max-h-[260px] space-y-2 overflow-y-auto pr-1">
        {runs.length === 0 && (
          <div className="rounded-2xl bg-gray-50 p-4 text-sm font-semibold text-gray-500">
            No test runs yet.
          </div>
        )}
        {runs.map((run) => (
          <button
            key={run.id}
            type="button"
            onClick={() => onSelectResult(run)}
            className={`w-full rounded-2xl px-4 py-3 text-left transition ${
              active?.id === run.id
                ? 'bg-coinnect-primary text-white'
                : 'bg-gray-50 text-gray-800 hover:bg-gray-100'
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <span className="min-w-0 truncate text-sm font-extrabold">
                {run.label}
              </span>
              <span className="shrink-0 text-xs font-black uppercase">
                {run.status}
              </span>
            </div>
            <p className="mt-1 text-xs opacity-75">{run.duration_ms} ms</p>
          </button>
        ))}
      </div>

      {active && (
        <div>
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="min-w-0 truncate font-extrabold">{active.label}</h3>
            <RunBadge state={active.status} />
          </div>
          {active.error && (
            <div className="mb-3 rounded-2xl bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
              {active.error}
            </div>
          )}

          {/* Display captured/processed image if present in response */}
          {active.response && (active.response.image_b64 || active.response.annotated_image_b64) && (
            <div className="mb-4 overflow-hidden rounded-2xl border border-gray-200 bg-gray-950 shadow-inner flex items-center justify-center">
              <img
                src={active.response.annotated_image_b64 || active.response.image_b64}
                alt="Processed Capture"
                className="w-full h-auto object-contain max-h-[300px]"
              />
            </div>
          )}

          <pre className="max-h-[200px] overflow-auto rounded-2xl bg-gray-950 p-4 text-xs leading-5 text-white">
            {JSON.stringify(active.response, null, 2)}
          </pre>
        </div>
      )}
    </section>
  );
}

function StatusLine({ icon, text }) {
  const IconComponent = icon;
  return (
    <div className="flex items-center gap-3">
      <IconComponent className="h-5 w-5 text-coinnect-primary" />
      <span>{text}</span>
    </div>
  );
}

export default App;
