import { useEffect, useState } from "react";
import { api } from "../api";

export type PanelSource = {
  panel_key: string;
  mode: "fake" | "push" | "http-health";
  allowed_modes: Array<"fake" | "push" | "http-health">;
  url: string | null;
  expected_status: number | null;
  timeout_seconds: number | null;
  has_secret: boolean;
  last_received_at: string | null;
  last_status: string | null;
};

type DataSources = {
  api_key: { prefix: string; created_at: string } | null;
  panels: PanelSource[];
};

const MODE_LABELS: Record<PanelSource["mode"], string> = {
  fake: "Fake",
  push: "Push",
  "http-health": "HTTP health",
};

export function DataSourceCard({
  slug,
  panelKey,
  token,
  onHealthStatus,
}: {
  slug: string;
  panelKey: string;
  token: string;
  onHealthStatus: (status: string | null) => void;
}) {
  const [data, setData] = useState<DataSources | null>(null);
  const [mode, setMode] = useState<PanelSource["mode"]>("fake");
  const [url, setUrl] = useState("");
  const [expectedStatus, setExpectedStatus] = useState("200");
  const [timeoutSeconds, setTimeoutSeconds] = useState("5");
  const [secret, setSecret] = useState("");
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setRevealedKey(null);
    setNotice(null);
    setError(null);
    api<DataSources>(`/api/projects/${slug}/data-sources`, {}, token)
      .then((body) => {
        if (cancelled) {
          return;
        }
        setData(body);
        const current = body.panels.find((item) => item.panel_key === panelKey);
        setMode(current?.mode ?? "fake");
        setUrl(current?.url ?? "");
        setExpectedStatus(String(current?.expected_status ?? 200));
        setTimeoutSeconds(String(current?.timeout_seconds ?? 5));
        setSecret("");
        onHealthStatus(panelKey === "system-health" ? (current?.last_status ?? null) : null);
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return;
        }
        setError(err instanceof Error ? err.message : "Could not load data sources");
        onHealthStatus(null);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, panelKey, token, onHealthStatus]);

  const current = data?.panels.find((item) => item.panel_key === panelKey);
  const allowed = current?.allowed_modes ?? ["fake", "push"];

  async function save(): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = { mode };
      if (mode === "http-health") {
        payload.url = url;
        payload.expected_status = Number(expectedStatus);
        payload.timeout_seconds = Number(timeoutSeconds);
        if (secret) {
          payload.secret = secret;
        }
      }
      const saved = await api<PanelSource>(
        `/api/projects/${slug}/panels/${panelKey}/data-source`,
        { method: "PUT", body: JSON.stringify(payload) },
        token,
      );
      setData((existing) =>
        existing
          ? { ...existing, panels: existing.panels.map((item) => (item.panel_key === panelKey ? saved : item)) }
          : existing,
      );
      setSecret("");
      if (panelKey === "system-health") {
        onHealthStatus(saved.last_status);
      }
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the data source");
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function onTest() {
    const saved = await save();
    if (!saved) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await api<{ ok: boolean; detail: string; last_received_at: string | null; last_status: string | null }>(
        `/api/projects/${slug}/panels/${panelKey}/test-connection`,
        { method: "POST" },
        token,
      );
      setNotice(result.detail);
      setData((existing) =>
        existing
          ? {
              ...existing,
              panels: existing.panels.map((item) =>
                item.panel_key === panelKey
                  ? { ...item, last_received_at: result.last_received_at, last_status: result.last_status, mode }
                  : item,
              ),
            }
          : existing,
      );
      if (panelKey === "system-health") {
        onHealthStatus(result.last_status);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not test the connection");
    } finally {
      setBusy(false);
    }
  }

  async function issueKey(rotate: boolean) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const issued = await api<{ key: string; prefix: string; created_at: string }>(
        rotate ? `/api/projects/${slug}/api-key/rotate` : `/api/projects/${slug}/api-key`,
        { method: "POST" },
        token,
      );
      setRevealedKey(issued.key);
      setData((existing) =>
        existing ? { ...existing, api_key: { prefix: issued.prefix, created_at: issued.created_at } } : existing,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not issue an API key");
    } finally {
      setBusy(false);
    }
  }

  async function revokeKey() {
    setBusy(true);
    setError(null);
    setRevealedKey(null);
    try {
      await api<void>(`/api/projects/${slug}/api-key`, { method: "DELETE" }, token);
      setData((existing) => (existing ? { ...existing, api_key: null } : existing));
      setNotice("API key revoked.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not revoke the API key");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="data-source">
      <h2>Data source</h2>
      <p className="lede">Read-only. Fake reads local fixtures. Push accepts this project's payload. HTTP health sends one GET.</p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label>
          Data source
          <select
            value={mode}
            onChange={(event) => {
              setMode(event.target.value as PanelSource["mode"]);
              setNotice(null);
            }}
          >
            {allowed.map((item) => (
              <option key={item} value={item}>
                {MODE_LABELS[item]}
              </option>
            ))}
          </select>
        </label>
        {mode === "http-health" ? (
          <>
            <label>
              URL
              <input value={url} onChange={(event) => setUrl(event.target.value)} autoComplete="off" />
            </label>
            <label>
              Expected status
              <input
                value={expectedStatus}
                inputMode="numeric"
                onChange={(event) => setExpectedStatus(event.target.value)}
              />
            </label>
            <label>
              Timeout (seconds)
              <input
                value={timeoutSeconds}
                inputMode="numeric"
                onChange={(event) => setTimeoutSeconds(event.target.value)}
              />
            </label>
            <label>
              Secret
              <input
                type="password"
                value={secret}
                autoComplete="off"
                placeholder={current?.has_secret ? "Leave blank to keep the saved secret" : ""}
                onChange={(event) => setSecret(event.target.value)}
              />
            </label>
          </>
        ) : null}
        <div className="modal-actions">
          <button type="submit" disabled={busy}>
            Save data source
          </button>
          <button type="button" className="ghost" disabled={busy} onClick={() => void onTest()}>
            Test connection
          </button>
        </div>
      </form>
      {current?.last_received_at ? <p>Last received {current.last_received_at}</p> : <p>Last received —</p>}
      {mode === "push" ? (
        <div className="key-actions">
          {data?.api_key ? <p>Active key {data.api_key.prefix}</p> : <p>No API key yet.</p>}
          {revealedKey ? (
            <p className="key-once" role="status">
              Copy this key. It is shown once: {revealedKey}
            </p>
          ) : null}
          <div className="modal-actions">
            <button type="button" disabled={busy || data?.api_key != null} onClick={() => void issueKey(false)}>
              Generate API key
            </button>
            <button type="button" className="ghost" disabled={busy || data?.api_key == null} onClick={() => void issueKey(true)}>
              Rotate API key
            </button>
            <button type="button" className="ghost" disabled={busy || data?.api_key == null} onClick={() => void revokeKey()}>
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
  );
}
