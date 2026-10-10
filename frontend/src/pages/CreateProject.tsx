import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api } from "../api";
import { useAuth } from "../auth";
import { useShell } from "../shell";
import type { PanelDef, Project } from "../types";

export function CreateProjectPage() {
  const { token } = useAuth();
  const { projects, setProjects } = useShell();
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<PanelDef[] | null>(null);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

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

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    if (selected.size === 0) {
      setError("Select at least one panel");
      return;
    }
    if (!token || !catalog) {
      return;
    }
    setError(null);
    setPending(true);
    try {
      const created = await api<Project>(
        "/api/projects",
        {
          method: "POST",
          body: JSON.stringify({ name: name.trim(), panels: [...selected] }),
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
      setPending(false);
    }
  }

  const groups = catalog ? [...new Set(catalog.map((panel) => panel.group))] : [];

  return (
    <main className="page">
      <p className="eyebrow">New project</p>
      <h1>Create a project</h1>
      <p className="lede">Name it, then turn on the panels it needs. Nothing here calls out to a data source yet.</p>
      <form onSubmit={onSubmit}>
        <label>
          Project name
          <input
            name="name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoComplete="off"
            required
          />
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
        <button type="submit" disabled={pending || !catalog}>
          {pending ? "Saving…" : "Confirm"}
        </button>
      </form>
    </main>
  );
}
