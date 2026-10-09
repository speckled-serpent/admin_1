import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { RevenueView } from "../components/RevenueView";
import { useShell } from "../shell";
import type { Revenue } from "../types";

const SALES_DATA = "sales-data";

export function ProjectPage() {
  const { slug } = useParams();
  const { token } = useAuth();
  const { projects } = useShell();
  const project = projects.find((item) => item.slug === slug);
  const [picked, setPicked] = useState<string | null>(null);
  const selected = project && picked && project.panels.includes(picked) ? picked : (project?.panels[0] ?? "");
  const [revenue, setRevenue] = useState<Revenue | null>(null);
  const [revenueState, setRevenueState] = useState<"idle" | "loading" | "ready" | "missing" | "error">("idle");
  const [revenueError, setRevenueError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !project || selected !== SALES_DATA) {
      setRevenue(null);
      setRevenueError(null);
      setRevenueState("idle");
      return;
    }
    let cancelled = false;
    setRevenueState("loading");
    api<Revenue>(`/api/projects/${project.slug}/revenue`, {}, token)
      .then((body) => {
        if (!cancelled) {
          setRevenue(body);
          setRevenueError(null);
          setRevenueState("ready");
        }
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        setRevenue(null);
        if (err instanceof ApiError && err.status === 404) {
          setRevenueState("missing");
          return;
        }
        setRevenueError(err instanceof Error ? err.message : "Could not load revenue");
        setRevenueState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [token, project, selected]);

  if (!project) {
    return (
      <main className="page">
        <h1>Project not found</h1>
      </main>
    );
  }

  const showRevenue = selected === SALES_DATA && revenueState === "ready" && revenue !== null;
  const waitingOnRevenue = selected === SALES_DATA && (revenueState === "idle" || revenueState === "loading");
  const showSoon = selected !== "" && !showRevenue && !waitingOnRevenue && revenueState !== "error";

  return (
    <div className="workspace">
      <aside className="rail">
        <p className="eyebrow">Panels</p>
        <nav aria-label="Panels">
          {project.panels.map((key) => (
            <button
              key={key}
              type="button"
              aria-current={key === selected ? "page" : undefined}
              onClick={() => setPicked(key)}
            >
              {labelFor(key)}
            </button>
          ))}
        </nav>
      </aside>
      <main className="workspace-main">
        <h1>{project.name}</h1>
        {revenueState === "loading" ? <p className="muted">Loading revenue…</p> : null}
        {revenueState === "error" && revenueError ? (
          <p className="form-error" role="alert">
            {revenueError}
          </p>
        ) : null}
        {showRevenue && revenue ? <RevenueView revenue={revenue} /> : null}
        {showSoon ? (
          <section className="coming-soon">
            <h2>Coming soon</h2>
            <p className="lede">{labelFor(selected)} is not wired to a data source yet.</p>
          </section>
        ) : null}
      </main>
    </div>
  );
}

function labelFor(key: string): string {
  const labels: Record<string, string> = {
    "system-health": "System health",
    performance: "Performance",
    logs: "Logs",
    "uptime-incidents": "Uptime & incidents",
    "deploys-releases": "Deploys/releases",
    "user-data": "User data",
    "sales-data": "Sales data",
    "consolidated-costs": "Consolidated costs",
    "product-metrics": "Product metrics",
    marketing: "Marketing",
    support: "Support",
    logistics: "Logistics",
  };
  return labels[key] ?? key;
}
