import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { PanelRail } from "../components/PanelRail";
import { RevenueView } from "../components/RevenueView";
import { labelFor } from "../panelLabels";
import { useShell } from "../shell";
import type { Revenue } from "../types";

const SALES_DATA = "sales-data";
const SYSTEM_HEALTH = "system-health";

export function ProjectPage() {
  const { slug, panel } = useParams();
  const { token } = useAuth();
  const { projects } = useShell();
  const project = projects.find((item) => item.slug === slug);
  const selected = project && panel && project.panels.includes(panel) ? panel : (project?.panels[0] ?? "");
  const [revenue, setRevenue] = useState<Revenue | null>(null);
  const [revenueState, setRevenueState] = useState<"idle" | "loading" | "ready" | "missing" | "error">("idle");
  const [revenueError, setRevenueError] = useState<string | null>(null);
  const [healthStatus, setHealthStatus] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    setHealthStatus(selected === SYSTEM_HEALTH ? undefined : null);
  }, [selected]);

  useEffect(() => {
    if (!token || !project || selected !== SYSTEM_HEALTH) {
      return;
    }
    let cancelled = false;
    api<{ last_status: string | null }>(`/api/projects/${project.slug}/panels/system-health/settings`, {}, token)
      .then((body) => {
        if (!cancelled) {
          setHealthStatus(body.last_status);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHealthStatus(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token, project, selected]);

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
  const showHealth = selected === SYSTEM_HEALTH && Boolean(healthStatus);
  const showSoon = selected !== "" && !showRevenue && !waitingOnRevenue && !showHealth && revenueState !== "error";

  return (
    <div className="workspace">
      <PanelRail project={project} selected={selected} />
      <main className="workspace-main">
        <h1>{project.name}</h1>
        {revenueState === "loading" ? <p className="muted">Loading revenue…</p> : null}
        {revenueState === "error" && revenueError ? (
          <p className="form-error" role="alert">
            {revenueError}
          </p>
        ) : null}
        {showRevenue && revenue ? <RevenueView revenue={revenue} /> : null}
        {showHealth ? (
          <section className="coming-soon">
            <h2>Latest status</h2>
            <p>{healthStatus}</p>
          </section>
        ) : null}
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
