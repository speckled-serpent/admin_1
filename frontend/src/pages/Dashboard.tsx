import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { chargeLabel, formatMinor, formatUnix } from "../format";
import type { Project, Revenue } from "../types";

type LoadState =
  | { kind: "loading" }
  | { kind: "empty" }
  | { kind: "ready"; username: string; revenue: Revenue }
  | { kind: "error"; message: string };

export function DashboardPage() {
  const { token, logout } = useAuth();
  const navigate = useNavigate();
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    if (!token) {
      return;
    }
    let cancelled = false;

    async function load(currentToken: string) {
      try {
        const me = await api<{ username: string }>("/api/auth/me", {}, currentToken);
        const projects = await api<Project[]>("/api/projects", {}, currentToken);
        if (projects.length === 0) {
          if (!cancelled) {
            setState({ kind: "empty" });
          }
          return;
        }
        const revenue = await api<Revenue>(`/api/projects/${projects[0].slug}/revenue`, {}, currentToken);
        if (!cancelled) {
          setState({ kind: "ready", username: me.username, revenue });
        }
      } catch (err) {
        if (cancelled) {
          return;
        }
        if (err instanceof ApiError && err.status === 401) {
          await logout();
          navigate("/login", { replace: true });
          return;
        }
        const message = err instanceof Error ? err.message : "Could not load revenue";
        setState({ kind: "error", message });
      }
    }

    void load(token);
    return () => {
      cancelled = true;
    };
  }, [token, logout, navigate]);

  async function onLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <p className="wordmark">
          <span className="mark" aria-hidden="true" />
          admin_1
        </p>
        <div className="topbar-actions">
          {state.kind === "ready" ? <span className="who">{state.username}</span> : null}
          <button type="button" className="ghost" onClick={() => void onLogout()}>
            Log out
          </button>
        </div>
      </header>
      <main className="page">
        {state.kind === "loading" ? <p className="muted">Loading revenue…</p> : null}
        {state.kind === "empty" ? <p>No projects are seeded yet.</p> : null}
        {state.kind === "error" ? (
          <p className="form-error" role="alert">
            {state.message}
          </p>
        ) : null}
        {state.kind === "ready" ? <RevenueView revenue={state.revenue} /> : null}
      </main>
    </div>
  );
}

function RevenueView({ revenue }: { revenue: Revenue }) {
  const currency = revenue.currency ?? "usd";
  return (
    <>
      <div className="page-heading">
        <p className="eyebrow">Project</p>
        <h1>{revenue.project.name}</h1>
        <p className="lede">Local revenue for this project. Captured charges, refunds, and what remains.</p>
      </div>
      <section className="stats" aria-label="Revenue totals">
        <article className="stat" aria-label="Gross">
          <p className="stat-label">Gross</p>
          <p className="stat-value">{formatMinor(revenue.gross_amount, currency)}</p>
          <p className="stat-note">{revenue.succeeded_count} succeeded charges</p>
        </article>
        <article className="stat" aria-label="Refunded">
          <p className="stat-label">Refunded</p>
          <p className="stat-value refund">{formatMinor(revenue.refunded_amount, currency)}</p>
          <p className="stat-note">{revenue.refunded_count} with a refund</p>
        </article>
        <article className="stat" aria-label="Net">
          <p className="stat-label">Net</p>
          <p className="stat-value">{formatMinor(revenue.net_amount, currency)}</p>
          <p className="stat-note">{revenue.charge_count} charges in the fixture</p>
        </article>
      </section>
      <section className="panel">
        <div className="panel-head">
          <h2>Charges</h2>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Description</th>
                <th>Status</th>
                <th className="num">Amount</th>
                <th className="num">Refunded</th>
              </tr>
            </thead>
            <tbody>
              {revenue.charges.map((charge) => (
                <tr key={charge.id}>
                  <td>{formatUnix(charge.created)}</td>
                  <td>
                    <div>{charge.description ?? charge.id}</div>
                    {charge.customer ? <div className="cell-sub">{charge.customer}</div> : null}
                  </td>
                  <td>
                    <span className={`pill pill-${chargeLabel(charge).replace(" ", "-")}`}>{chargeLabel(charge)}</span>
                  </td>
                  <td className="num">{formatMinor(charge.amount, charge.currency)}</td>
                  <td className="num">
                    {charge.amount_refunded > 0 ? formatMinor(charge.amount_refunded, charge.currency) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
