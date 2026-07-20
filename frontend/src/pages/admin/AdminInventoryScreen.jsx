import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Check,
  History,
  LogOut,
  Minus,
  Plus,
  Save,
} from "lucide-react";

import { API_BASE } from "../../constants/api";
import { ROUTES } from "../../constants/routes";

const TOKEN_KEY = "coinnect_admin_token";

const SECTIONS = [
  {
    key: "bill_dispenser_counts",
    location: "BILL_DISPENSER",
    title: "Bill dispensers",
    description: "Cash available for customer payouts",
  },
  {
    key: "coin_counts",
    location: "COIN_DISPENSER",
    title: "Coin dispensers",
    description: "Coins available for exact change",
  },
  {
    key: "bill_storage_counts",
    location: "BILL_STORAGE",
    title: "Accepted cash storage",
    description: "Bills stored from customer deposits",
  },
];

function displayDenomination(denomination) {
  if (denomination === "USD" || denomination === "EUR") {
    return denomination;
  }
  const [currency, value] = denomination.split("_");
  const symbol = currency === "PHP" ? "₱" : currency === "USD" ? "$" : "€";
  return `${symbol}${value}`;
}

function accessibleDenomination(denomination) {
  return denomination.replace("_", " ");
}

function authHeaders() {
  return {
    Authorization: `Bearer ${sessionStorage.getItem(TOKEN_KEY) || ""}`,
  };
}

export default function AdminInventoryScreen() {
  const navigate = useNavigate();
  const [inventory, setInventory] = useState(null);
  const [draft, setDraft] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState(false);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  // New claims state
  const [activeTab, setActiveTab] = useState("reconciliation"); // "reconciliation" | "claims"
  const [claims, setClaims] = useState([]);
  const [loadingClaims, setLoadingClaims] = useState(false);
  const [resolvingClaim, setResolvingClaim] = useState(null);
  const [resolutionNotes, setResolutionNotes] = useState("");
  const [resolvingError, setResolvingError] = useState("");
  const [resolvingSaving, setResolvingSaving] = useState(false);

  const leaveForExpiredSession = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    navigate(ROUTES.HOME, { replace: true });
  }, [navigate]);

  const request = useCallback(
    async (path, options = {}) => {
      const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers: {
          ...authHeaders(),
          ...(options.body ? { "Content-Type": "application/json" } : {}),
          ...options.headers,
        },
      });
      if (response.status === 401) {
        leaveForExpiredSession();
        throw new Error("Admin session expired");
      }
      const body = response.status === 204 ? null : await response.json();
      if (!response.ok) {
        throw new Error(body?.detail || "Request failed");
      }
      return body;
    },
    [leaveForExpiredSession]
  );

  const loadClaims = useCallback(async () => {
    setLoadingClaims(true);
    try {
      const data = await request("/admin/claims");
      setClaims(data?.claims || []);
    } catch (err) {
      console.error("Failed to load claims", err);
    } finally {
      setLoadingClaims(false);
    }
  }, [request]);

  const resolveClaim = async (claimCode) => {
    setResolvingSaving(true);
    setResolvingError("");
    try {
      await request(`/admin/claims/${claimCode}/resolve`, {
        method: "POST",
        body: JSON.stringify({
          resolution_notes: resolutionNotes,
        }),
      });
      setResolvingClaim(null);
      setResolutionNotes("");
      setMessage("Claim resolved successfully");
      loadClaims();
    } catch (err) {
      setResolvingError(err.message);
    } finally {
      setResolvingSaving(false);
    }
  };

  const load = useCallback(async () => {
    try {
      const [current, audit] = await Promise.all([
        request("/inventory/"),
        request("/inventory/adjustments?source=ADMIN&limit=50"),
      ]);
      setInventory(current);
      setDraft(current);
      setHistory(audit.adjustments);
    } catch (err) {
      if (err.message !== "Admin session expired") setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [request]);

  useEffect(() => {
    if (activeTab === "claims") {
      loadClaims();
    }
  }, [activeTab, loadClaims]);

  useEffect(() => {
    if (!sessionStorage.getItem(TOKEN_KEY)) {
      navigate(ROUTES.ADMIN_LOGIN, { replace: true });
      return;
    }
    load();
  }, [load, navigate]);

  const changes = useMemo(() => {
    if (!inventory || !draft) return [];
    return SECTIONS.flatMap((section) => {
      const draftSec = draft[section.key] || {};
      const invSec = inventory[section.key] || {};
      return Object.entries(draftSec).flatMap(([denomination, count]) => {
        const previous = invSec[denomination];
        return count !== previous
          ? [{
              location: section.location,
              denomination,
              count,
              previous,
            }]
          : [];
      });
    });
  }, [draft, inventory]);

  const updateCount = (sectionKey, denomination, value) => {
    const count = Math.max(0, Number.parseInt(value || "0", 10) || 0);
    setDraft((current) => ({
      ...current,
      [sectionKey]: {
        ...current[sectionKey],
        [denomination]: count,
      },
    }));
    setMessage("");
  };

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      const updated = await request("/inventory/", {
        method: "PUT",
        body: JSON.stringify({
          updates: changes.map((change) => ({
            location: change.location,
            denomination: change.denomination,
            count: change.count,
          })),
          reason,
          note: note.trim() || null,
        }),
      });
      setInventory(updated);
      setDraft(updated);
      setReviewing(false);
      setReason("");
      setNote("");
      setMessage("Inventory updated");
      const audit = await request(
        "/inventory/adjustments?source=ADMIN&limit=50"
      );
      setHistory(audit.adjustments);
    } catch (err) {
      if (err.message !== "Admin session expired") setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const logout = async () => {
    try {
      await request("/admin/session", { method: "DELETE" });
    } catch {
      // A locally cleared session is safe even if the server already expired it.
    }
    sessionStorage.removeItem(TOKEN_KEY);
    navigate(ROUTES.HOME, { replace: true });
  };

  if (loading || !draft) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-coinnect-navy text-white">
        <p className="text-xl font-semibold">Loading maintenance inventory…</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-surface-light text-gray-900">
      <header className="sticky top-0 z-20 bg-coinnect-navy px-6 py-4 text-white shadow-lg lg:px-10">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-5">
          <div className="flex items-center gap-4">
            <img
              src="/assets/Coinnect Logo White.png"
              alt="Coinnect"
              className="h-10 w-auto"
            />
            <div className="border-l border-white/20 pl-4">
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-coinnect-primary-light">
                Maintenance mode
              </p>
              <h1 className="text-xl font-bold">Cash inventory</h1>
            </div>
          </div>
          <button
            type="button"
            onClick={logout}
            className="flex min-h-12 items-center gap-2 rounded-button border border-white/30 px-5 font-semibold hover:bg-white/10"
          >
            <LogOut className="h-5 w-5" />
            Exit admin
          </button>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-8 px-5 py-8 lg:grid-cols-[1fr_340px] lg:px-10">
        <div className="space-y-9">
          {/* Tabs Navigation */}
          <div className="flex border-b border-gray-200 gap-4 mb-6">
            <button
              type="button"
              onClick={() => setActiveTab("reconciliation")}
              className={`pb-4 px-2 font-bold text-lg border-b-2 transition-colors ${
                activeTab === "reconciliation"
                  ? "border-coinnect-primary text-coinnect-primary-dark"
                  : "border-transparent text-gray-500 hover:text-gray-900"
              }`}
            >
              Inventory Reconciliation
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("claims")}
              className={`pb-4 px-2 font-bold text-lg border-b-2 transition-colors flex items-center gap-2 ${
                activeTab === "claims"
                  ? "border-coinnect-primary text-coinnect-primary-dark"
                  : "border-transparent text-gray-500 hover:text-gray-900"
              }`}
            >
              Claims Resolution
              {claims?.length > 0 && (
                <span className="bg-red-500 text-white rounded-full text-xs px-2.5 py-0.5 font-extrabold">
                  {claims.length}
                </span>
              )}
            </button>
          </div>

          {activeTab === "reconciliation" ? (
            <>
              <div>
                <p className="text-sm font-bold uppercase tracking-[0.2em] text-coinnect-primary">
                  Physical reconciliation
                </p>
                <h2 className="mt-2 text-3xl font-extrabold lg:text-4xl">
                  Count what is actually loaded
                </h2>
                <p className="mt-2 text-gray-600">
                  Values replace the recorded count. Changed rows are highlighted.
                </p>
              </div>

              {SECTIONS.map((section) => (
                <section key={section.key}>
                  <div className="mb-4 flex items-end justify-between gap-4">
                    <div>
                      <h3 className="text-2xl font-bold">{section.title}</h3>
                      <p className="text-sm text-gray-500">{section.description}</p>
                    </div>
                    <span className="text-sm font-semibold text-gray-500">
                      {Object.keys(draft[section.key] || {}).length} locations
                    </span>
                  </div>
                  <div className="overflow-hidden rounded-card border border-gray-200 bg-white">
                    {Object.entries(draft[section.key] || {}).map(
                      ([denomination, count], index) => {
                        const changed =
                          count !== inventory?.[section.key]?.[denomination];
                        const controlName =
                          section.location === "BILL_STORAGE"
                            ? `Storage ${accessibleDenomination(denomination)}`
                            : accessibleDenomination(denomination);
                        return (
                          <div
                            key={denomination}
                            className={`grid grid-cols-[1fr_auto] items-center gap-4 px-5 py-4 transition-colors lg:px-6 ${
                              index ? "border-t border-gray-100" : ""
                            } ${changed ? "bg-orange-50" : ""}`}
                          >
                            <div>
                              <p className="text-xl font-extrabold">
                                {displayDenomination(denomination)}
                              </p>
                              <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                                {denomination.replaceAll("_", " ")}
                              </p>
                            </div>
                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                aria-label={`Decrease ${controlName}`}
                                onClick={() =>
                                  updateCount(section.key, denomination, count - 1)
                                }
                                className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-100 hover:bg-gray-200"
                              >
                                <Minus className="h-5 w-5" />
                              </button>
                              <input
                                aria-label={`${controlName} count`}
                                type="number"
                                min="0"
                                inputMode="numeric"
                                value={count}
                                onChange={(event) =>
                                  updateCount(
                                    section.key,
                                    denomination,
                                    event.target.value
                                  )
                                }
                                className={`h-12 w-24 rounded-xl border-2 text-center text-xl font-bold outline-none ${
                                  changed
                                    ? "border-coinnect-primary text-coinnect-primary-dark"
                                    : "border-gray-200"
                                }`}
                              />
                              <button
                                type="button"
                                aria-label={`Increase ${controlName}`}
                                onClick={() =>
                                  updateCount(section.key, denomination, count + 1)
                                }
                                className="flex h-12 w-12 items-center justify-center rounded-full bg-gray-100 hover:bg-gray-200"
                              >
                                <Plus className="h-5 w-5" />
                              </button>
                            </div>
                          </div>
                        );
                      }
                    )}
                  </div>
                </section>
              ))}
            </>
          ) : (
            <div className="space-y-6">
              <div>
                <p className="text-sm font-bold uppercase tracking-[0.2em] text-coinnect-primary">
                  Unresolved Customer Issues
                </p>
                <h2 className="mt-2 text-3xl font-extrabold lg:text-4xl">
                  Active Claim Tickets
                </h2>
                <p className="mt-2 text-gray-600">
                  Review and resolve shortfalls or failed transaction obligations.
                </p>
              </div>

              {loadingClaims ? (
                <p className="text-gray-500 font-semibold">Loading active claims…</p>
              ) : (!claims || claims.length === 0) ? (
                <div className="rounded-card border border-gray-200 bg-white p-8 text-center text-gray-500 font-semibold shadow-sm">
                  No active claim tickets found. Kiosk balances are verified!
                </div>
              ) : (
                <div className="grid gap-6">
                  {claims.map((claim) => (
                    <article
                      key={claim.claim_ticket_code}
                      className="rounded-card border border-gray-200 bg-white p-6 shadow-sm space-y-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-3 flex-wrap">
                            <span className="font-extrabold text-2xl font-mono text-coinnect-primary-dark">
                              {claim.claim_ticket_code}
                            </span>
                            <span
                              className={`rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider ${
                                claim.type.includes("ewallet")
                                  ? "bg-blue-100 text-blue-800"
                                  : claim.type.includes("forex")
                                  ? "bg-purple-100 text-purple-805"
                                  : "bg-green-100 text-green-800"
                              }`}
                            >
                              {claim.type}
                            </span>
                          </div>
                          <p className="mt-2 text-sm text-gray-500">
                            ID: <span className="font-mono">{claim.transaction_id}</span>
                          </p>
                          <p className="mt-1 text-xs text-gray-400">
                            Created at: {new Date(claim.created_at).toLocaleString()}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-xs font-bold text-gray-400 uppercase tracking-wide">
                            Shortfall Owed
                          </p>
                          <p className="text-3xl font-black text-red-600">
                            ₱{claim.shortfall}
                          </p>
                          <p className="text-xs text-gray-500 mt-1">
                            Inserted: ₱{claim.inserted_amount} | Dispensed: ₱{claim.dispensed_amount}
                          </p>
                        </div>
                      </div>

                      <div className="grid gap-4 border-t border-gray-150 pt-4 md:grid-cols-2">
                        <div className="space-y-1">
                          <p className="text-xs font-bold text-gray-400 uppercase tracking-wide">
                            Transaction Details
                          </p>
                          {claim.provider && (
                            <p className="text-sm font-semibold">
                              Provider: <span className="capitalize">{claim.provider}</span> ({claim.direction})
                            </p>
                          )}
                          {claim.mobile_number && (
                            <p className="text-sm">
                              Mobile: <span className="font-mono">{claim.mobile_number}</span>
                            </p>
                          )}
                          {claim.account_name && (
                            <p className="text-sm">
                              Account Name: <span className="font-semibold">{claim.account_name}</span>
                            </p>
                          )}
                          {!claim.provider && <p className="text-sm text-gray-650 font-semibold">Cash Conversion swap</p>}
                        </div>
                        <div className="space-y-1">
                          <p className="text-xs font-bold text-gray-400 uppercase tracking-wide">
                            Error Information
                          </p>
                          <p className="text-sm font-bold text-red-700">
                            {claim.error_code || "UNKNOWN_ERROR"}
                          </p>
                          <p className="text-xs text-gray-600">
                            {claim.error_message || "No error details available"}
                          </p>
                        </div>
                      </div>

                      <div className="flex justify-end pt-2 border-t border-gray-100">
                        <button
                          type="button"
                          onClick={() => {
                            setResolvingClaim(claim.claim_ticket_code);
                            setResolutionNotes("");
                            setResolvingError("");
                          }}
                          className="flex min-h-11 items-center gap-2 rounded-button bg-coinnect-primary px-5 font-bold text-white hover:bg-coinnect-primary-dark"
                        >
                          Resolve Claim
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <aside className="space-y-6 lg:sticky lg:top-28 lg:self-start">
          <section className="rounded-card bg-coinnect-navy p-6 text-white">
            <p className="text-sm font-bold uppercase tracking-widest text-coinnect-primary-light">
              Pending changes
            </p>
            <p className="mt-3 text-5xl font-extrabold">{changes.length}</p>
            <p className="mt-1 text-sm text-slate-300">
              inventory locations changed
            </p>
            <button
              type="button"
              disabled={!changes.length}
              onClick={() => setReviewing(true)}
              className="mt-6 flex min-h-14 w-full items-center justify-center gap-2 rounded-button bg-coinnect-primary px-5 font-bold disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Save className="h-5 w-5" />
              Save inventory
            </button>
            {message && (
              <p className="mt-4 flex items-center gap-2 font-semibold text-green-300">
                <Check className="h-5 w-5" />
                {message}
              </p>
            )}
          </section>

          <section className="rounded-card bg-white p-6">
            <div className="mb-4 flex items-center gap-2">
              <History className="h-5 w-5 text-coinnect-primary" />
              <h3 className="font-bold">Recent adjustments</h3>
            </div>
            <div className="max-h-[430px] space-y-4 overflow-y-auto pr-1">
              {history.length === 0 ? (
                <p className="text-sm text-gray-500">
                  Manual changes will appear here.
                </p>
              ) : (
                history.map((item) => (
                  <article
                    key={item.id}
                    className="border-b border-gray-100 pb-4 last:border-0"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-bold">
                        {displayDenomination(item.denomination)}
                      </p>
                      <span
                        className={`font-bold ${
                          item.delta >= 0 ? "text-green-600" : "text-red-600"
                        }`}
                      >
                        {item.delta >= 0 ? "+" : ""}
                        {item.delta}
                      </span>
                    </div>
                    <p className="mt-1 text-xs font-semibold uppercase tracking-wider text-gray-400">
                      {item.reason.replaceAll("_", " ")}
                    </p>
                    <p className="mt-1 text-xs text-gray-500">
                      {new Date(item.created_at).toLocaleString()}
                    </p>
                  </article>
                ))
              )}
            </div>
          </section>
        </aside>
      </div>

      {reviewing && (
        <section className="fixed inset-x-0 bottom-0 z-30 border-t border-gray-200 bg-white shadow-[0_-20px_50px_rgba(14,21,31,0.18)]">
          <div className="mx-auto grid max-w-7xl gap-6 px-6 py-6 lg:grid-cols-[1fr_420px] lg:px-10">
            <div>
              <p className="text-sm font-bold uppercase tracking-widest text-coinnect-primary">
                Review before saving
              </p>
              <div className="mt-4 grid max-h-48 gap-2 overflow-y-auto sm:grid-cols-2">
                {changes.map((change) => (
                  <div
                    key={`${change.location}-${change.denomination}`}
                    className="flex items-center justify-between rounded-xl bg-gray-50 px-4 py-3"
                  >
                    <span className="font-bold">
                      {accessibleDenomination(change.denomination)}
                    </span>
                    <span className="font-semibold text-coinnect-primary-dark">
                      {change.previous} → {change.count}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div className="space-y-3">
              <label className="block">
                <span className="mb-1 block text-sm font-bold">
                  Adjustment reason
                </span>
                <select
                  aria-label="Adjustment reason"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  className="h-12 w-full rounded-xl border-2 border-gray-200 px-3 font-semibold"
                >
                  <option value="">Select reason</option>
                  <option value="REFILL">Refill</option>
                  <option value="PHYSICAL_COUNT">Physical count</option>
                  <option value="CORRECTION">Correction</option>
                </select>
              </label>
              <input
                aria-label="Adjustment note"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="Optional note"
                className="h-12 w-full rounded-xl border-2 border-gray-200 px-3"
              />
              {error && (
                <p className="flex items-center gap-2 text-sm font-semibold text-red-600">
                  <AlertTriangle className="h-4 w-4" />
                  {error}
                </p>
              )}
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setReviewing(false)}
                  className="min-h-12 flex-1 rounded-button border-2 border-gray-300 font-bold"
                >
                  Continue editing
                </button>
                <button
                  type="button"
                  disabled={!reason || saving}
                  onClick={save}
                  className="min-h-12 flex-1 rounded-button bg-coinnect-primary px-5 font-bold text-white disabled:opacity-40"
                >
                  {saving ? "Saving…" : "Confirm changes"}
                </button>
              </div>
            </div>
          </div>
        </section>
      )}

      {resolvingClaim && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-card bg-white p-6 shadow-2xl space-y-6">
            <div>
              <h3 className="text-2xl font-bold text-gray-900">Resolve Claim Ticket</h3>
              <p className="text-sm text-gray-500 mt-1">
                Marking ticket <span className="font-mono font-bold text-coinnect-primary">{resolvingClaim}</span> as resolved.
              </p>
            </div>
            
            <div className="space-y-3">
              <label className="block">
                <span className="mb-1 block text-sm font-bold text-gray-700">
                  Resolution Notes
                </span>
                <textarea
                  required
                  rows={4}
                  value={resolutionNotes}
                  onChange={(event) => setResolutionNotes(event.target.value)}
                  placeholder="Describe the action taken (e.g. 'Cleared bill jam in slot 3 and paid user ₱500 via GCash manually')"
                  className="w-full rounded-xl border-2 border-gray-200 p-3 outline-none focus:border-coinnect-primary"
                />
              </label>
              
              {resolvingError && (
                <p className="flex items-center gap-2 text-sm font-semibold text-red-600">
                  <AlertTriangle className="h-4 w-4" />
                  {resolvingError}
                </p>
              )}
            </div>
            
            <div className="flex gap-3 justify-end border-t border-gray-150 pt-4">
              <button
                type="button"
                onClick={() => setResolvingClaim(null)}
                className="min-h-12 px-5 rounded-button border-2 border-gray-300 font-bold hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!resolutionNotes.trim() || resolvingSaving}
                onClick={() => resolveClaim(resolvingClaim)}
                className="min-h-12 px-5 rounded-button bg-coinnect-primary font-bold text-white hover:bg-coinnect-primary-dark disabled:opacity-40"
              >
                {resolvingSaving ? "Saving…" : "Mark as Resolved"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
