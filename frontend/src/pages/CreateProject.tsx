import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { useShell } from "../shell";
import type { PanelDef, Project } from "../types";

type Step = "panels" | "sources";
type Kind = "push" | "http-health";

type Draft = {
  key: string;
  name: string;
  kind: Kind;
  url: string;
  expectedStatus: string;
  timeoutSeconds: string;
  secret: string;
};

type Pending = {
  name: string;
  kind: Kind;
  url: string;
  expectedStatus: string;
  timeoutSeconds: string;
  secret: string;
};

function blankPending(): Pending {
  return { name: "", kind: "push", url: "", expectedStatus: "200", timeoutSeconds: "5", secret: "" };
}

export function CreateProjectPage() {
  const { token } = useAuth();
  const { projects, setProjects } = useShell();
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<PanelDef[] | null>(null);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [step, setStep] = useState<Step>("panels");
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [pending, setPending] = useState<Record<string, Pending>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!token) {
      return;
    }
    let cancelled = false;
    api<PanelDef[]>("/api/panel-catalog", {}, token)
      .then((panels) => {
        if (!cancelled) {
          setCatalog(panels);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load panels");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  function toggle(key: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function onPanelsSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    if (selected.size === 0) {
      setError("Select at least one panel");
      return;
    }
    setError(null);
    setStep("sources");
  }

  function addConnection(panelKey: string) {
    const draft = pending[panelKey] ?? blankPending();
    if (!draft.name.trim()) {
      setError("Name is required");
      return;
    }
    if (draft.kind === "http-health" && !draft.url.trim()) {
      setError("URL is required");
      return;
    }
    const key = `c${drafts.length + 1}`;
    setDrafts((current) => [
      ...current,
      {
        key,
        name: draft.name.trim(),
        kind: draft.kind,
        url: draft.url.trim(),
        expectedStatus: draft.expectedStatus,
        timeoutSeconds: draft.timeoutSeconds,
        secret: draft.secret,
      },
    ]);
    setChoices((current) => ({ ...current, [panelKey]: key }));
    setPending((current) => ({ ...current, [panelKey]: blankPending() }));
    setError(null);
  }

  async function onSourcesSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !catalog) {
      return;
    }
    const chosen = catalog.filter((panel) => selected.has(panel.key));
    if (chosen.some((panel) => (choices[panel.key] ?? "fake") === "new")) {
      setError("Add the connection or choose Fake");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      const created = await api<Project>(
        "/api/projects",
        {
          method: "POST",
          body: JSON.stringify({
            name: name.trim(),
            panels: chosen.map((panel) => panel.key),
            connections: drafts.map((draft) => ({
              key: draft.key,
              name: draft.name,
              kind: draft.kind,
              url: draft.kind === "http-health" ? draft.url : null,
              expected_status: draft.kind === "http-health" ? Number(draft.expectedStatus) : null,
              timeout_seconds: draft.kind === "http-health" ? Number(draft.timeoutSeconds) : null,
              secret: draft.kind === "http-health" && draft.secret ? draft.secret : null,
            })),
            sources: chosen.map((panel) => {
              const choice = choices[panel.key] ?? "fake";
              if (choice === "fake") {
                return { panel: panel.key, mode: "fake", connection: null };
              }
              const draft = drafts.find((item) => item.key === choice);
              return { panel: panel.key, mode: draft?.kind ?? "push", connection: choice };
            }),
          }),
        },
        token,
      );
      const next = [...projects.filter((project) => project.slug !== created.slug), created].sort((a, b) =>
        a.name.localeCompare(b.name),
      );
      setProjects(next);
      navigate(`/projects/${created.slug}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the project");
    } finally {
      setSaving(false);
    }
  }

  const groups = catalog ? [...new Set(catalog.map((panel) => panel.group))] : [];
  const chosen = catalog ? catalog.filter((panel) => selected.has(panel.key)) : [];

  if (step === "sources") {
    return (
      <main className="page">
        <p className="eyebrow">New project</p>
        <h1>Select data sources</h1>
        <p className="lede">Each panel can stay on Fake, use a connection you add here, or reuse one from earlier in this step.</p>
        <form onSubmit={(event) => void onSourcesSubmit(event)}>
          <div className="source-list">
            {chosen.map((panel) => {
              const choice = choices[panel.key] ?? "fake";
              const usable = drafts.filter((draft) => panel.key === "system-health" || draft.kind === "push");
              const creating = pending[panel.key] ?? blankPending();
              return (
                <fieldset key={panel.key} className="source-row">
                  <legend>{panel.label}</legend>
                  <label>
                    {panel.label} source
                    <select
                      aria-label={`${panel.label} source`}
                      value={choice}
                      onChange={(event) => setChoices((current) => ({ ...current, [panel.key]: event.target.value }))}
                    >
                      <option value="fake">Fake</option>
                      {usable.map((draft) => (
                        <option key={draft.key} value={draft.key}>
                          {draft.name}
                        </option>
                      ))}
                      <option value="new">Create new connection</option>
                    </select>
                  </label>
                  {choice === "new" ? (
                    <>
                      <label>
                        Connection name for {panel.label}
                        <input
                          value={creating.name}
                          autoComplete="off"
                          onChange={(event) =>
                            setPending((current) => ({
                              ...current,
                              [panel.key]: { ...creating, name: event.target.value },
                            }))
                          }
                        />
                      </label>
                      {panel.key === "system-health" ? (
                        <label>
                          Connection kind
                          <select
                            aria-label={`Connection kind for ${panel.label}`}
                            value={creating.kind}
                            onChange={(event) =>
                              setPending((current) => ({
                                ...current,
                                [panel.key]: { ...creating, kind: event.target.value as Kind },
                              }))
                            }
                          >
                            <option value="push">Push</option>
                            <option value="http-health">HTTP health</option>
                          </select>
                        </label>
                      ) : null}
                      {panel.key === "system-health" && creating.kind === "http-health" ? (
                        <>
                          <label>
                            URL
                            <input
                              value={creating.url}
                              autoComplete="off"
                              onChange={(event) =>
                                setPending((current) => ({
                                  ...current,
                                  [panel.key]: { ...creating, url: event.target.value },
                                }))
                              }
                            />
                          </label>
                          <label>
                            Expected status
                            <input
                              value={creating.expectedStatus}
                              inputMode="numeric"
                              onChange={(event) =>
                                setPending((current) => ({
                                  ...current,
                                  [panel.key]: { ...creating, expectedStatus: event.target.value },
                                }))
                              }
                            />
                          </label>
                          <label>
                            Timeout (seconds)
                            <input
                              value={creating.timeoutSeconds}
                              inputMode="numeric"
                              onChange={(event) =>
                                setPending((current) => ({
                                  ...current,
                                  [panel.key]: { ...creating, timeoutSeconds: event.target.value },
                                }))
                              }
                            />
                          </label>
                        </>
                      ) : null}
                      <button type="button" onClick={() => addConnection(panel.key)}>
                        Add connection
                      </button>
                    </>
                  ) : null}
                </fieldset>
              );
            })}
          </div>
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
          <div className="modal-actions">
            <button
              type="button"
              className="ghost"
              onClick={() => {
                setError(null);
                setStep("panels");
              }}
            >
              Back
            </button>
            <button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Confirm"}
            </button>
          </div>
        </form>
      </main>
    );
  }

  return (
    <main className="page">
      <p className="eyebrow">New project</p>
      <h1>Create a project</h1>
      <p className="lede">Name it, then turn on the panels it needs. You choose where each panel gets its data on the next step.</p>
      <form onSubmit={onPanelsSubmit}>
        <label>
          Project name
          <input name="name" value={name} onChange={(event) => setName(event.target.value)} autoComplete="off" required />
        </label>
        {catalog ? (
          <div className="panel-groups">
            {groups.map((group) => (
              <fieldset key={group} className="panel-group">
                <legend>{group}</legend>
                {group === "Users" ? <p className="group-note">Daily, new, and monthly returning.</p> : null}
                <div className="toggle-grid">
                  {catalog
                    .filter((panel) => panel.group === group)
                    .map((panel) => (
                      <button
                        key={panel.key}
                        type="button"
                        className="toggle"
                        aria-pressed={selected.has(panel.key)}
                        onClick={() => toggle(panel.key)}
                      >
                        {panel.label}
                      </button>
                    ))}
                </div>
              </fieldset>
            ))}
          </div>
        ) : (
          <p className="muted">Loading panels…</p>
        )}
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
        <button type="submit" disabled={!catalog}>
          Next
        </button>
      </form>
    </main>
  );
}
