import { Link } from "react-router-dom";
import { useShell } from "../shell";

export function OverviewPage() {
  const { projects } = useShell();

  if (projects.length === 0) {
    return (
      <main className="page empty-state">
        <h1>No projects started yet. Create one</h1>
        <Link className="text-button" to="/create">
          Create new project
        </Link>
      </main>
    );
  }

  return (
    <main className="page">
      <p className="eyebrow">All projects</p>
      <h1>Overview</h1>
      <p className="lede">Consolidated totals are not built yet. Open a project tab to see its panels.</p>
    </main>
  );
}
