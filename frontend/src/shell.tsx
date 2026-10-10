import { createContext, useContext, useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { ApiError, api } from "./api";
import { useAuth } from "./auth";
import type { Project } from "./types";

type ShellValue = {
  username: string;
  projects: Project[];
  setProjects: (projects: Project[]) => void;
};

const ShellContext = createContext<ShellValue | null>(null);

export function useShell(): ShellValue {
  const value = useContext(ShellContext);
  if (!value) {
    throw new Error("useShell must be used inside the authenticated shell");
  }
  return value;
}

export function Shell() {
  const { token, logout } = useAuth();
  const navigate = useNavigate();
  const [value, setValue] = useState<ShellValue | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      return;
    }
    let cancelled = false;

    async function load(currentToken: string) {
      try {
        const me = await api<{ username: string }>("/api/auth/me", {}, currentToken);
        const projects = await api<Project[]>("/api/projects", {}, currentToken);
        if (!cancelled) {
          setValue({
            username: me.username,
            projects,
            setProjects(next) {
              setValue((current) => (current ? { ...current, projects: next } : current));
            },
          });
          setError(null);
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
        setError(err instanceof Error ? err.message : "Could not load projects");
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
        <nav className="project-tabs" aria-label="Projects">
          <NavLink to="/" end className={({ isActive }) => (isActive ? "tab active" : "tab")}>
            Overview
          </NavLink>
          {value?.projects.map((project) => (
            <NavLink
              key={project.slug}
              to={`/projects/${project.slug}`}
              className={({ isActive }) => (isActive ? "tab active" : "tab")}
            >
              {project.name}
            </NavLink>
          ))}
        </nav>
        <div className="topbar-actions">
          {value ? <span className="who">{value.username}</span> : null}
          <button type="button" className="ghost" onClick={() => void onLogout()}>
            Log out
          </button>
        </div>
      </header>
      {error ? (
        <p className="page form-error" role="alert">
          {error}
        </p>
      ) : null}
      {value ? (
        <ShellContext.Provider value={value}>
          <Outlet />
        </ShellContext.Provider>
      ) : error ? null : (
        <p className="page muted">Loading…</p>
      )}
      <NavLink to="/create" className="create-fab" aria-label="Create New Project">
        +
      </NavLink>
    </div>
  );
}
