import ForexIntakeReview from "./ForexIntakeReview";
import ForexClaimCard from "./ForexClaimCard";
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
  const [forexAudit, setForexAudit] = useState([]);
  const [forexIntakes, setForexIntakes] = useState([]);
  const [retainedCash, setRetainedCash] = useState([]);
  const [intakeOperations, setIntakeOperations] = useState([]);
  const [intakeResolution, setIntakeResolution] = useState(null);
  const [intakeError, setIntakeError] = useState("");
  const [intakeSaving, setIntakeSaving] = useState(false);
  const [intakeSuccess, setIntakeSuccess] = useState("");
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
      const audit = await request("/admin/forex-audit");
      setForexAudit(audit.records || []);
      const pending = await request("/admin/forex-intakes");
      setForexIntakes(pending.items || []);
      setRetainedCash(data?.retained_cash || []);
      setIntakeOperations(data?.intake_operations || []);
      setClaims((data?.claims || []).map(claim => ({ ...claim,
        type: claim.type || (claim.source_kind === "EWALLET" ? "ewallet" : claim.source_kind?.toLowerCase()) || "transaction",
        shortfall: claim.shortfall ?? claim.amount,
        dispensed_amount: claim.dispensed_amount ?? claim.confirmed_dispensed_amount,
        error_code: claim.error_code || claim.reason_code,
        error_message: claim.error_message || claim.reason_message,
      })));
    } catch (err) {
      console.error("Failed to load claims", err);
    } finally {
      setLoadingClaims(false);
    }
  }, [request]);

  // Fee management state
  const [feesState, setFeesState] = useState(null);
  const [loadingFees, setLoadingFees] = useState(false);
  const [savingFees, setSavingFees] = useState(false);
  const [feesMsg, setFeesMsg] = useState("");
  const [feesErr, setFeesErr] = useState("");

  const loadFees = useCallback(async () => {
    setLoadingFees(true);
    setFeesErr("");
    try {
      const data = await request("/admin/fees");
      setFeesState(data);
    } catch (err) {
      setFeesErr(err.message || "Failed to load fee configuration");
    } finally {
      setLoadingFees(false);
    }
  }, [request]);

  const saveFees = async () => {
    if (!feesState) return;
    setSavingFees(true);
    setFeesMsg("");
    setFeesErr("");
    try {
      const updated = await request("/admin/fees", {
        method: "PUT",
        body: JSON.stringify(feesState),
      });
      setFeesState(updated);
      setFeesMsg("Fee settings updated successfully");
    } catch (err) {
      setFeesErr(err.message || "Failed to update fee settings");
    } finally {
      setSavingFees(false);
    }
  };

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

  const focusInspection = useCallback((element) => {
    if (element) {
      element.focus({ preventScroll: true });
      element.scrollIntoView?.({ block: "center" });
    }
  }, []);

  const openInspection = (operation) => {
    setIntakeSuccess("");
    setIntakeResolution({ ...operation, actual_dispensed_count: 0, retained: false,
      counts: { "1": 0, "5": 0, "10": 0, "20": 0, ...operation.counts }, notes: "" });
    setIntakeError("");
  };

  const inspectClaim = (claim) => {
    const operation = intakeOperations.find(item => item.transaction_id === claim.transaction_id);
    if (operation) {
      setError("");
      openInspection(operation);
    } else {
      setError("No pending physical operation was found for this claim. Refresh the claims list; if it remains provisional, its recovery records need review before settlement.");
    }
  };

  const reconcileIntake = async () => {
    if (intakeSaving) return;
    setIntakeError("");
    const notes = intakeResolution.notes.trim();
    if (notes.length < 5) {
      setIntakeError("Enter inspection notes with at least 5 characters before saving.");
      return;
    }
    const payout = intakeResolution.medium === "PAYOUT";
    if (payout && (!Number.isInteger(intakeResolution.actual_dispensed_count)
      || intakeResolution.actual_dispensed_count < 0
      || intakeResolution.actual_dispensed_count > intakeResolution.requested_count)) {
      setIntakeError(`Enter a whole number from 0 to ${intakeResolution.requested_count} for the pieces dispensed.`);
      return;
    }
    setIntakeSaving(true);
    try {
      await request(payout ? `/admin/physical-operations/${intakeResolution.id}/reconcile` : `/admin/ewallet/intakes/${intakeResolution.id}/reconcile`, {
        method: "POST", body: JSON.stringify(payout ? { actual_dispensed_count: intakeResolution.actual_dispensed_count, resolution_notes: notes } : { ...intakeResolution, notes }),
      });
      setIntakeResolution(null);
      setIntakeSuccess("Physical inspection saved. Review the updated claim for any remaining amount owed.");
      await loadClaims();
    } catch (err) { setIntakeError(err.message); }
    finally { setIntakeSaving(false); }
  };

  const reconcilePayment = async (claim) => {
    setError("");
    try {
      await request(`/admin/ewallet/${claim.transaction_id}/reconcile`, { method: "POST" });
      await loadClaims();
    } catch (err) { setError(err.message); }
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
    } else if (activeTab === "fees") {
      loadFees();
    }
  }, [activeTab, loadClaims, loadFees]);

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
            <button
              type="button"
              onClick={() => setActiveTab("fees")}
              className={`pb-4 px-2 font-bold text-lg border-b-2 transition-colors ${
                activeTab === "fees"
                  ? "border-coinnect-primary text-coinnect-primary-dark"
                  : "border-transparent text-gray-500 hover:text-gray-900"
              }`}
            >
              Fee Management
            </button>
          </div>

          {activeTab === "reconciliation" && (
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
          )}

          {activeTab === "claims" && (
            <div className="space-y-6">
              {intakeSuccess && <p role="status" className="font-semibold text-green-800">{intakeSuccess}</p>}
              {error && <p role="alert" className="font-semibold text-red-700">{error}</p>}
              {forexIntakes.map(intake => <ForexIntakeReview key={intake.id} intake={intake} request={request} reload={loadClaims} />)}
              {forexAudit.length > 0 && <details className="rounded-xl border border-amber-300 p-4"><summary>Legacy forex records requiring review ({forexAudit.length})</summary>
                <p>Do not settle legacy scalar totals. Review per-currency physical evidence first.</p>
                {forexAudit.map(row => <pre key={row.transaction_id} className="whitespace-pre-wrap text-sm border-t mt-3">{JSON.stringify(row, null, 2)}</pre>)}
              </details>}

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

              {retainedCash.length > 0 && <section className="rounded-xl border border-amber-300 bg-amber-50 p-5">
                <h3 className="font-bold">Abandoned cash retained — separate from fees and claims</h3>
                <p>Total: ₱{retainedCash.reduce((sum, row) => sum + row.amount, 0)}</p>
                {retainedCash.map(row => <p key={row.transaction_id}>{row.transaction_id}: ₱{row.amount}</p>)}
              </section>}
              {intakeOperations.map(operation => <section key={`${operation.medium}:${operation.id}`} className="rounded-xl border border-amber-300 p-5">
                <p>Uncertain {operation.medium === "PAYOUT" ? "payout" : `${operation.medium.toLowerCase()} intake`} · {operation.transaction_id}</p>
                <button type="button" className="min-h-11 font-bold underline" onClick={() => openInspection(operation)}>Record physical inspection</button>
              </section>)}
              {intakeResolution && <section key={intakeResolution.id} tabIndex={-1} ref={focusInspection} className="rounded-xl border-2 border-amber-500 p-5 space-y-3">
                <h3 className="font-bold">Confirm physical cash movement</h3>
                <p>Transaction: {intakeResolution.transaction_id}</p>
                <p>Inspect the cash path and storage before recording the result. Previously confirmed credits cannot be removed.</p>
                {intakeResolution.medium === "PAYOUT" ? <label className="flex gap-3">Confirmed {intakeResolution.denomination} pieces dispensed (requested {intakeResolution.requested_count})<input type="number" min="0" max={intakeResolution.requested_count} value={intakeResolution.actual_dispensed_count} onChange={e => setIntakeResolution({ ...intakeResolution, actual_dispensed_count: Number(e.target.value) })} /></label>
                  : intakeResolution.medium === "BILL" ? <label className="flex gap-3"><input type="checkbox" checked={intakeResolution.retained} onChange={e => setIntakeResolution({ ...intakeResolution, retained: e.target.checked })} />The ₱{intakeResolution.value} bill was stored</label>
                  : [1, 5, 10, 20].map(denom => <label key={denom} className="flex gap-3">₱{denom} total coins in this session<input type="number" min="0" max="1000" value={intakeResolution.counts[denom]} onChange={e => setIntakeResolution({ ...intakeResolution, counts: { ...intakeResolution.counts, [denom]: Number(e.target.value) } })} /></label>)}
                <label className="block">Inspection notes<textarea className="block w-full border p-2" value={intakeResolution.notes} onChange={e => setIntakeResolution({ ...intakeResolution, notes: e.target.value })} /></label>
                <p className="text-sm">Required: describe what you inspected and found (at least 5 characters).</p>
                {intakeError && <p role="alert">{intakeError}</p>}
                <button type="button" className="min-h-11 font-bold underline mr-5 disabled:opacity-50" disabled={intakeSaving} onClick={reconcileIntake}>{intakeSaving ? "Saving verified counts…" : "Save verified counts"}</button>
                <button type="button" className="min-h-11 underline" disabled={intakeSaving} onClick={() => setIntakeResolution(null)}>Cancel inspection</button>
              </section>}
              {loadingClaims ? (
                <p className="text-gray-500 font-semibold">Loading active claims…</p>
              ) : (!claims || claims.length === 0) ? (
                <div className="rounded-card border border-gray-200 bg-white p-8 text-center text-gray-500 font-semibold shadow-sm">
                  No active claim tickets found.
                </div>
              ) : (
                <div className="grid gap-6">
                  {claims.map((claim) => claim.items ? <ForexClaimCard key={claim.claim_ticket_code} claim={claim} request={request} reload={loadClaims} /> : (
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
                            if (claim.status === "PROVISIONAL" && claim.source_kind !== "EWALLET") { inspectClaim(claim); return; }
                            if (claim.status === "PROVISIONAL") { reconcilePayment(claim); return; }
                            setResolvingClaim(claim.claim_ticket_code);
                            setResolutionNotes("");
                            setResolvingError("");
                          }}
                          className="flex min-h-11 items-center gap-2 rounded-button bg-coinnect-primary px-5 font-bold text-white hover:bg-coinnect-primary-dark"
                        >
                          {claim.status === "PROVISIONAL"
                            ? claim.source_kind === "EWALLET" ? "Verify payment status" : "Review physical counts"
                            : "Resolve Claim"}
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === "fees" && (
            <div className="space-y-6">
              <div>
                <p className="text-sm font-bold uppercase tracking-[0.2em] text-coinnect-primary">
                  Machine fee configuration
                </p>
                <h2 className="mt-2 text-3xl font-extrabold lg:text-4xl">
                  Manage Transaction Fees
                </h2>
                <p className="mt-2 text-gray-600">
                  Update transaction fee amounts for money converter, e-wallet, and forex exchanges.
                </p>
              </div>

              {loadingFees ? (
                <div className="p-8 text-center text-gray-500 bg-white rounded-card">
                  Loading fee settings…
                </div>
              ) : !feesState ? (
                <div className="p-8 text-center text-red-500 bg-white rounded-card">
                  Failed to load fee configuration.
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Money Converter Fees */}
                  <section className="rounded-card border border-gray-200 bg-white p-6">
                    <h3 className="text-xl font-bold text-gray-900 mb-4 border-b pb-2">
                      Money Converter Fees (Fixed ₱)
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      <div>
                        <label className="block text-sm font-bold text-gray-700 mb-2">
                          Bill-to-Bill Fee (₱)
                        </label>
                        <input
                          type="number"
                          min="0"
                          value={feesState.fee_bill_to_bill ?? 10}
                          onChange={(e) =>
                            setFeesState((prev) => ({
                              ...prev,
                              fee_bill_to_bill: Number(e.target.value),
                            }))
                          }
                          className="w-full rounded-xl border-2 border-gray-200 p-3 font-bold text-lg focus:border-coinnect-primary outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-bold text-gray-700 mb-2">
                          Bill-to-Coin Fee (₱)
                        </label>
                        <input
                          type="number"
                          min="0"
                          value={feesState.fee_bill_to_coin ?? 15}
                          onChange={(e) =>
                            setFeesState((prev) => ({
                              ...prev,
                              fee_bill_to_coin: Number(e.target.value),
                            }))
                          }
                          className="w-full rounded-xl border-2 border-gray-200 p-3 font-bold text-lg focus:border-coinnect-primary outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-bold text-gray-700 mb-2">
                          Coin-to-Bill Fee (₱)
                        </label>
                        <input
                          type="number"
                          min="0"
                          value={feesState.fee_coin_to_bill ?? 3}
                          onChange={(e) =>
                            setFeesState((prev) => ({
                              ...prev,
                              fee_coin_to_bill: Number(e.target.value),
                            }))
                          }
                          className="w-full rounded-xl border-2 border-gray-200 p-3 font-bold text-lg focus:border-coinnect-primary outline-none"
                        />
                      </div>
                    </div>
                  </section>

                  {/* Forex Fees */}
                  <section className="rounded-card border border-gray-200 bg-white p-6">
                    <h3 className="text-xl font-bold text-gray-900 mb-4 border-b pb-2">
                      Foreign Exchange Fees (Percentage %)
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                      <div>
                        <label className="block text-xs font-bold uppercase text-gray-500 mb-2">
                          USD → PHP Fee (%)
                        </label>
                        <input
                          type="number"
                          step="0.1"
                          min="0"
                          value={feesState.forex_fees?.["usd-to-php"] ?? 5.0}
                          onChange={(e) =>
                            setFeesState((prev) => ({
                              ...prev,
                              forex_fees: {
                                ...prev.forex_fees,
                                "usd-to-php": Number(e.target.value),
                              },
                            }))
                          }
                          className="w-full rounded-xl border-2 border-gray-200 p-3 font-bold text-lg focus:border-coinnect-primary outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold uppercase text-gray-500 mb-2">
                          PHP → USD Fee (%)
                        </label>
                        <input
                          type="number"
                          step="0.1"
                          min="0"
                          value={feesState.forex_fees?.["php-to-usd"] ?? 5.0}
                          onChange={(e) =>
                            setFeesState((prev) => ({
                              ...prev,
                              forex_fees: {
                                ...prev.forex_fees,
                                "php-to-usd": Number(e.target.value),
                              },
                            }))
                          }
                          className="w-full rounded-xl border-2 border-gray-200 p-3 font-bold text-lg focus:border-coinnect-primary outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold uppercase text-gray-500 mb-2">
                          EUR → PHP Fee (%)
                        </label>
                        <input
                          type="number"
                          step="0.1"
                          min="0"
                          value={feesState.forex_fees?.["eur-to-php"] ?? 5.0}
                          onChange={(e) =>
                            setFeesState((prev) => ({
                              ...prev,
                              forex_fees: {
                                ...prev.forex_fees,
                                "eur-to-php": Number(e.target.value),
                              },
                            }))
                          }
                          className="w-full rounded-xl border-2 border-gray-200 p-3 font-bold text-lg focus:border-coinnect-primary outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold uppercase text-gray-500 mb-2">
                          PHP → EUR Fee (%)
                        </label>
                        <input
                          type="number"
                          step="0.1"
                          min="0"
                          value={feesState.forex_fees?.["php-to-eur"] ?? 5.0}
                          onChange={(e) =>
                            setFeesState((prev) => ({
                              ...prev,
                              forex_fees: {
                                ...prev.forex_fees,
                                "php-to-eur": Number(e.target.value),
                              },
                            }))
                          }
                          className="w-full rounded-xl border-2 border-gray-200 p-3 font-bold text-lg focus:border-coinnect-primary outline-none"
                        />
                      </div>
                    </div>
                  </section>

                  {/* Save Fee Settings */}
                  <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t">
                    <div>
                      {feesMsg && (
                        <p className="flex items-center gap-2 text-sm font-bold text-green-600">
                          <Check className="h-5 w-5" /> {feesMsg}
                        </p>
                      )}
                      {feesErr && (
                        <p className="flex items-center gap-2 text-sm font-bold text-red-600">
                          <AlertTriangle className="h-5 w-5" /> {feesErr}
                        </p>
                      )}
                    </div>
                    <button
                      type="button"
                      disabled={savingFees}
                      onClick={saveFees}
                      className="min-h-12 rounded-button bg-coinnect-primary px-8 font-bold text-white shadow-md hover:bg-coinnect-primary-dark disabled:opacity-40"
                    >
                      {savingFees ? "Saving Fee Settings…" : "Save Fee Settings"}
                    </button>
                  </div>
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
