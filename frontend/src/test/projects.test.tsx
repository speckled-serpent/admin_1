import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { AuthProvider } from "../auth";
import type { PanelDef, Project } from "../types";

const catalog: PanelDef[] = [
  { key: "system-health", label: "System health", group: "Server", description: "Whether the project is up." },
  { key: "logs", label: "Logs", group: "Server", description: "Recent log lines." },
  { key: "user-data", label: "User data", group: "Users", description: "Daily active, new, and monthly returning." },
  { key: "sales-data", label: "Sales data", group: "Financials", description: "Sales and revenue." },
  { key: "consolidated-costs", label: "Consolidated costs", group: "Financials", description: "Cost lines." },
  { key: "logistics", label: "Logistics", group: "Optional", description: "Orders and shipments." },
];

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>,
  );
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("projects", () => {
  it("shows the empty state and the floating create button", async () => {
    sessionStorage.setItem("admin1.token", "test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/auth/me") {
          return json({ username: "dev" });
        }
        if (url === "/api/projects") {
          return json([]);
        }
        throw new Error(`unexpected fetch ${url}`);
      }),
    );

    renderAt("/");

    expect(await screen.findByRole("heading", { name: "No projects started yet. Create one" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create new project" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create New Project" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Overview" })).toBeInTheDocument();
  });

  it("creates a project and opens its tab", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("admin1.token", "test-token");
    const projects: Project[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/auth/me") {
          return json({ username: "dev" });
        }
        if (url === "/api/panel-catalog") {
          return json(catalog);
        }
        if (url === "/api/projects" && init?.method === "POST") {
          const body = JSON.parse(String(init.body)) as { name: string; panels: string[] };
          const created: Project = { slug: "lumen", name: body.name, panels: ["system-health"] };
          projects.push(created);
          return json(created, 201);
        }
        if (url === "/api/projects") {
          return json(projects);
        }
        throw new Error(`unexpected fetch ${url}`);
      }),
    );

    renderAt("/");
    await user.click(await screen.findByRole("link", { name: "Create new project" }));
    await user.type(await screen.findByLabelText("Project name"), "Lumen");
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Select at least one panel");

    await user.click(screen.getByRole("button", { name: "System health" }));
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    expect(await screen.findByRole("heading", { name: "Lumen" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Lumen" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Panels" })).toHaveTextContent("System health");
    expect(screen.getByRole("heading", { name: "Coming soon" })).toBeInTheDocument();
  });

  it("lists selected panels in the rail", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("admin1.token", "test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/auth/me") {
          return json({ username: "dev" });
        }
        if (url === "/api/projects") {
          return json([{ slug: "lumen", name: "Lumen", panels: ["system-health", "logs"] }]);
        }
        throw new Error(`unexpected fetch ${url}`);
      }),
    );

    renderAt("/projects/lumen");

    const rail = await screen.findByRole("navigation", { name: "Panels" });
    expect(rail).toHaveTextContent("System health");
    expect(rail).toHaveTextContent("Logs");
    expect(screen.getByRole("heading", { name: "Coming soon" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Logs" }));
    expect(screen.getByRole("button", { name: "Logs" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("heading", { name: "Coming soon" })).toBeInTheDocument();
    expect(screen.getByText("Logs is not wired to a data source yet.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Create New Project" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete project" })).toBeInTheDocument();
  });
});
