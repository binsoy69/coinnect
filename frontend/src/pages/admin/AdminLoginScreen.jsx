import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";

import VirtualKeypad from "../../components/common/VirtualKeypad";
import { API_BASE } from "../../constants/api";
import { ROUTES } from "../../constants/routes";

const TOKEN_KEY = "coinnect_admin_token";

export default function AdminLoginScreen() {
  const navigate = useNavigate();
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const login = async () => {
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE}/admin/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin }),
      });
      const body = await response.json();
      if (!response.ok) {
        throw new Error(body.detail || "Unable to enter maintenance");
      }
      sessionStorage.setItem(TOKEN_KEY, body.token);
      navigate(ROUTES.ADMIN_INVENTORY, { replace: true });
    } catch (err) {
      setError(err.message);
      setPin("");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="min-h-screen bg-coinnect-navy text-white">
      <div className="mx-auto grid min-h-screen max-w-6xl lg:grid-cols-[0.9fr_1.1fr]">
        <section className="flex flex-col justify-between p-8 lg:p-14">
          <button
            type="button"
            onClick={() => navigate(ROUTES.HOME)}
            className="w-fit text-left"
          >
            <img
              src="/assets/Coinnect Logo White.png"
              alt="Coinnect"
              className="h-12 w-auto"
            />
          </button>

          <div className="max-w-md py-10">
            <div className="mb-7 flex h-16 w-16 items-center justify-center rounded-full bg-coinnect-primary">
              <ShieldCheck className="h-8 w-8" />
            </div>
            <p className="mb-3 text-sm font-bold uppercase tracking-[0.24em] text-coinnect-primary-light">
              Restricted access
            </p>
            <h1 className="text-4xl font-extrabold leading-tight lg:text-6xl">
              Maintenance inventory
            </h1>
            <p className="mt-5 max-w-sm text-lg leading-relaxed text-slate-300">
              Enter the technician PIN to reconcile physical cash counts.
              Customer transactions pause while this session is open.
            </p>
          </div>

          <p className="text-sm text-slate-500">
            Exit maintenance when counting is complete.
          </p>
        </section>

        <section className="flex items-center justify-center bg-surface-light p-6 text-gray-900 lg:p-12">
          <div className="w-full max-w-xl rounded-card bg-surface-white p-7 shadow-xl lg:p-10">
            <div className="mb-7">
              <p className="text-sm font-semibold uppercase tracking-widest text-coinnect-primary">
                Technician verification
              </p>
              <h2 className="mt-2 text-3xl font-bold">Enter admin PIN</h2>
            </div>

            <VirtualKeypad
              value={pin}
              onChange={setPin}
              onSubmit={login}
              maxLength={8}
              placeholder="••••"
              submitLabel={submitting ? "Checking…" : "Enter maintenance"}
              colorClass="coinnect-primary"
              mask
            />

            {error && (
              <p
                role="alert"
                className="mt-5 rounded-xl bg-red-50 px-4 py-3 text-center font-semibold text-red-700"
              >
                {error}
              </p>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
