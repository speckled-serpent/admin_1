import { FormEvent, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { PanelRail } from "../components/PanelRail";
import { labelFor } from "../panelLabels";
import { useShell } from "../shell";

type Mode = "fake" | "push" | "http-health";

type Connection = {
  id: number;
  name: string;
  kind: Mode;
  url: string | null;
  expected_status: number | null;
  timeout_seconds: number | null;
  has_secret: boolean;
  api_key: { prefix: string; created_at: string } | null;
  last_received_at: string | null;
  last_status: string | null;
};

type PanelSettings = {
  panel_key: string;
  mode: Mode;
  connection_id: number | null;
  allowed_modes: Mode[];
  last_received_at: string | null;
  last_status: string | null;
  connections: Connection[];
};

const MODE_LABELS: Record<Mode, string> = {
  fake: "Fake",
  push: "Push",
  "http-health": "HTTP health",
};

export function PanelSettingsPage() {
  const { slug, panel } = useParams();
  const { token } = useAuth();
  const { projects } = useShell();
  const project = projects.find((item) => item.slug === slug);
  const panelKey = panel ?? "";
  const enabled = Boolean(project && project.panels.includes(panelKey));

  const [settings, setSettings] = useState<PanelSettings | null>(null);
  const [mode, setMode] = useState<Mode>("fake");
  const [connectionChoice, setConnectionChoice] = useState("new");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [expectedStatus, setExpectedStatus] = useState("200");
  const [timeoutSeconds, setTimeoutSeconds] = useState("5");
  const [secret, setSecret] = useState("");
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token || !project || !enabled) {
      return;
    }
    let cancelled = false;
    setRevealedKey(null);
    setNotice(null);
    setError(null);
    api<PanelSettings>(`/api/projects/${project.slug}/panels/${panelKey}/settings`, {}, token)
      .then((body) => {
        if (cancelled) {
          return;
        }
        setSettings(body);
        setMode(body.mode);
        setConnectionChoice(body.connection_id == null ? "new" : String(body.connection_id));
        setName("");
        setUrl("");
        setExpectedStatus("200");
        setTimeoutSeconds("5");
        setSecret("");
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Could not load settings");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token, project, enabled, panelKey]);

  if (!project) {
    return (
      <main className="page">
        <h1>Project not found</h1>
      </main>
    );
  }
  if (!enabled) {
    return (
      <div className="workspace">
        <PanelRail project={project} selected="" />
        <main className="workspace-main">
          <h1>Panel not found</h1>
        </main>
      </div>
    );
  }

  const projectSlug = project.slug;
  const allowed = settings?.allowed_modes ?? ["fake", "push"];
  const matching = (settings?.connections ?? []).filter((item) => item.kind === mode);
  const active = matching.find((item) => String(item.id) === connectionChoice) ?? null;

  function payload(): Record<string, unknown> {
    if (mode === "fake") {
      return { mode: "fake" };
    }
    if (connectionChoice !== "new" && active) {
      return { mode, connection_id: active.id };
    }
    const created: Record<string, unknown> = { name: name.trim(), kind: mode };
    if (mode === "http-health") {
      created.url = url;
      created.expected_status = Number(expectedStatus);
      created.timeout_seconds = Number(timeoutSeconds);
      if (secret) {
        created.secret = secret;
      }
    }
    return { mode, new_connection: created };
  }

  async function save(): Promise<PanelSettings | null> {
    if (!token) {
      return null;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = await api<PanelSettings>(
        `/api/projects/${projectSlug}/panels/${panelKey}/settings`,
        { method: "PUT", body: JSON.stringify(payload()) },
        token,
      );
      setSettings(saved);
      setMode(saved.mode);
      setConnectionChoice(saved.connection_id == null ? "new" : String(saved.connection_id));
      setName("");
      setSecret("");
      return saved;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the data source");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await save();
  }

  async function onTest() {
    const saved = await save();
    if (!saved || !token || !project) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api<{ ok: boolean; detail: string; last_received_at: string | null; last_status: string | null }>(
        `/api/projects/${projectSlug}/panels/${panelKey}/test-connection`,
        { method: "POST" },
        token,
      );
      setNotice(result.detail);
      setSettings({ ...saved, last_received_at: result.last_received_at, last_status: result.last_status });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not test the connection");
    } finally {
      setBusy(false);
    }
  }

  async function issueKey(rotate: boolean) {
    if (!token || !active) {
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const issued = await api<{ key: string; prefix: string; created_at: string }>(
        rotate
          ? `/api/projects/${projectSlug}/connections/${active.id}/api-key/rotate`
          : `/api/projects/${projectSlug}/connections/${active.id}/api-key`,
        { method: "POST" },
        token,
      );
      setRevealedKey(issued.key);
      setSettings((current) =>
        current
          ? {
              ...current,
              connections: current.connections.map((item) =>
                item.id === active.id ? { ...item, api_key: { prefix: issued.prefix, created_at: issued.created_at } } : item,
              ),
            }
          : current,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not issue an API key");
    } finally {
      setBusy(false);
    }
  }

  async function revokeKey() {
    if (!token || !active) {
      return;
    }
    setBusy(true);
    setError(null);
    setRevealedKey(null);
    try {
      await api<void>(`/api/projects/${projectSlug}/connections/${active.id}/api-key`, { method: "DELETE" }, token);
      setSettings((current) =>
        current
          ? {
              ...current,
              connections: current.connections.map((item) => (item.id === active.id ? { ...item, api_key: null } : item)),
            }
          : current,
      );
      setNotice("API key revoked.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not revoke the API key");
    } finally {
      setBusy(false);
    }
  }

  const received = settings?.last_received_at;

  return (
    <div className="workspace">
      <PanelRail project={project} selected={panelKey} />
      <main className="workspace-main">
        <p className="eyebrow">{project.name}</p>
        <h1>{labelFor(panelKey)} settings</h1>
        <section className="data-source">
          <h2>Data source</h2>
          <p className="lede">
            Fake reads local fixtures. Push and HTTP health use a project connection, which other panels can share.
          </p>
          <form onSubmit={(event) => void onSubmit(event)}>
            <label>
              Data source
              <select
                value={mode}
                onChange={(event) => {
                  const next = event.target.value as Mode;
                  setMode(next);
                  setNotice(null);
                  const first = (settings?.connections ?? []).find((item) => item.kind === next);
                  setConnectionChoice(first ? String(first.id) : "new");
                }}
              >
                {allowed.map((item) => (
                  <option key={item} value={item}>
                    {MODE_LABELS[item]}
                  </option>
                ))}
              </select>
            </label>
            {mode !== "fake" ? (
              <label>
                Connection
                <select value={matching.some((item) => String(item.id) === connectionChoice) ? connectionChoice : "new"} onChange={(event) => setConnectionChoice(event.target.value)}>
                  {matching.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                  <option value="new">Create new connection</option>
                </select>
              </label>
            ) : null}
            {mode !== "fake" && !active ? (
              <>
                <label>
                  Connection name
                  <input value={name} onChange={(event) => setName(event.target.value)} autoComplete="off" />
                </label>
                {mode === "http-health" ? (
                  <>
                    <label>
                      URL
                      <input value={url} onChange={(event) => setUrl(event.target.value)} autoComplete="off" />
                    </label>
                    <label>
                      Expected status
                      <input value={expectedStatus} inputMode="numeric" onChange={(event) => setExpectedStatus(event.target.value)} />
                    </label>
                    <label>
                      Timeout (seconds)
                      <input value={timeoutSeconds} inputMode="numeric" onChange={(event) => setTimeoutSeconds(event.target.value)} />
                    </label>
                    <label>
                      Secret
                      <input type="password" value={secret} autoComplete="off" onChange={(event) => setSecret(event.target.value)} />
                    </label>
                  </>
                ) : null}
              </>
            ) : null}
            <div className="modal-actions">
              <button type="submit" disabled={busy || !settings}>
                Save data source
              </button>
              <button type="button" className="ghost" disabled={busy || !settings} onClick={() => void onTest()}>
                Test connection
              </button>
            </div>
          </form>
          {received ? <p>Last received {received}</p> : <p>Last received —</p>}
          {mode === "push" && active ? (
            <div className="key-actions">
              {active.api_key ? <p>Active key {active.api_key.prefix}</p> : <p>No API key yet.</p>}
              {revealedKey ? (
                <p className="key-once" role="status">
                  Copy this key. It is shown once: {revealedKey}
                </p>
              ) : null}
              <div className="modal-actions">
                <button type="button" disabled={busy || active.api_key != null} onClick={() => void issueKey(false)}>
                  Generate API key
                </button>
                <button type="button" className="ghost" disabled={busy || active.api_key == null} onClick={() => void issueKey(true)}>
                  Rotate API key
                </button>
                <button type="button" className="ghost" disabled={busy || active.api_key == null} onClick={() => void revokeKey()}>
                  Revoke API key
                </button>
              </div>
            </div>
          ) : null}
          {notice ? <p role="status">{notice}</p> : null}
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
        </section>
        {panelKey === "system-health" && settings?.last_status ? (
          <section className="coming-soon">
            <h2>Latest status</h2>
            <p>{settings.last_status}</p>
          </section>
        ) : null}
      </main>
    </div>
  );
}
