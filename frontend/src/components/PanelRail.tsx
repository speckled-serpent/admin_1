import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { labelFor } from "../panelLabels";
import { useShell } from "../shell";
import type { Project } from "../types";
import { DeletePhraseDialog } from "./DeletePhraseDialog";

export function PanelRail({ project, selected }: { project: Project; selected: string }) {
  const navigate = useNavigate();
  const { token } = useAuth();
  const { projects, setProjects } = useShell();
  const [dialog, setDialog] = useState<"project" | "panel" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function close() {
    if (!busy) {
      setDialog(null);
      setError(null);
    }
  }

  async function confirmProject() {
    if (!token || busy) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api<void>(`/api/projects/${project.slug}`, { method: "DELETE" }, token);
      setProjects(projects.filter((item) => item.slug !== project.slug));
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete project");
      setBusy(false);
    }
  }

  async function confirmPanel() {
    if (!token || busy || !selected) {
      return;
    }
    setBusy(true);
    setError(null);
    const index = project.panels.indexOf(selected);
    const remaining = project.panels.filter((key) => key !== selected);
    const next = remaining[index] ?? remaining[index - 1] ?? null;
    try {
      await api<void>(`/api/projects/${project.slug}/panels/${selected}`, { method: "DELETE" }, token);
      setDialog(null);
      setBusy(false);
      setProjects(projects.map((item) => (item.slug === project.slug ? { ...item, panels: remaining } : item)));
      if (next) {
        navigate(`/projects/${project.slug}/panels/${next}`);
      } else {
        navigate("/");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete panel");
      setBusy(false);
    }
  }

  return (
    <aside className="rail">
      <p className="eyebrow">Panels</p>
      <nav aria-label="Panels">
        {project.panels.map((key) => (
          <div className="rail-row" key={key}>
            <button
              type="button"
              aria-current={key === selected ? "page" : undefined}
              onClick={() => navigate(`/projects/${project.slug}/panels/${key}`)}
            >
              {labelFor(key)}
            </button>
            <Link className="rail-cog" to={`/projects/${project.slug}/panels/${key}/settings`} aria-label={`${labelFor(key)} settings`}>
              <span aria-hidden="true">⚙</span>
            </Link>
          </div>
        ))}
      </nav>
      <div className="rail-actions">
        {selected ? (
          <button
            type="button"
            className="rail-delete"
            onClick={() => {
              setError(null);
              setDialog("panel");
            }}
          >
            Delete panel
          </button>
        ) : null}
        <button
          type="button"
          className="rail-delete"
          onClick={() => {
            setError(null);
            setDialog("project");
          }}
        >
          Delete project
        </button>
      </div>
      {dialog === "project" ? (
        <DeletePhraseDialog
          title={`Delete ${project.name}?`}
          lede="This removes the project and its panels. Type DELETE to confirm."
          titleId="delete-project-title"
          busy={busy}
          error={error}
          onCancel={close}
          onConfirm={() => void confirmProject()}
        />
      ) : null}
      {dialog === "panel" ? (
        <DeletePhraseDialog
          title={`Delete ${labelFor(selected)}?`}
          lede="This removes the panel from the project. Type DELETE to confirm."
          titleId="delete-panel-title"
          busy={busy}
          error={error}
          onCancel={close}
          onConfirm={() => void confirmPanel()}
        />
      ) : null}
    </aside>
  );
}
