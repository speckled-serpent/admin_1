import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { AuthProvider } from "../auth";

type Connection = {
  id: number;
  name: string;
  kind: string;
  url: string | null;
  expected_status: number | null;
  timeout_seconds: number | null;
  has_secret: boolean;
  api_key: { prefix: string; created_at: string } | null;
  last_received_at: string | null;
  last_status: string | null;
};

const state: {
  connections: Connection[];
  health: { mode: string; connection_id: number | null; last_received_at: string | null; last_status: string | null };
  logs: { mode: string; connection_id: number | null; last_received_at: string | null; last_status: string | null };
} = {
  connections: [],
  health: { mode: "fake", connection_id: null, last_received_at: null, last_status: null },
  logs: { mode: "fake", connection_id: null, last_received_at: null, last_status: null },
};

function settingsFor(panel: "system-health" | "logs") {
  const current = panel === "logs" ? state.logs : state.health;
  return {
    panel_key: panel,
    mode: current.mode,
    connection_id: current.connection_id,
    allowed_modes: panel === "system-health" ? ["fake", "push", "http-health"] : ["fake", "push"],
    last_received_at: current.last_received_at,
    last_status: current.last_status,
    connections: state.connections,
  };
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
  state.connections = [];
  state.health = { mode: "fake", connection_id: null, last_received_at: null, last_status: null };
  state.logs = { mode: "fake", connection_id: null, last_received_at: null, last_status: null };
});

function installFetch() {
  const calls: Array<{ url: string; method: string; body: unknown }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ url, method, body });
      if (url === "/api/auth/me") {
        return json({ username: "dev" });
      }
      if (url === "/api/projects") {
        return json([{ slug: "harbor", name: "Harbor", panels: ["system-health", "logs"] }]);
      }
      if (url === "/api/projects/harbor/panels/system-health/settings" && method === "GET") {
        return json(settingsFor("system-health"));
      }
      if (url === "/api/projects/harbor/panels/logs/settings" && method === "GET") {
        return json(settingsFor("logs"));
      }
      if (url.endsWith("/settings") && method === "PUT") {
        const panel = url.includes("/logs/") ? state.logs : state.health;
        const key = url.includes("/logs/") ? "logs" : "system-health";
        const update = body as {
          mode: string;
          connection_id?: number;
          new_connection?: { name: string; kind: string; url?: string | null };
        };
        if (update.new_connection) {
          const created: Connection = {
            id: 7,
            name: update.new_connection.name,
            kind: update.new_connection.kind,
            url: update.new_connection.url ?? null,
            expected_status: null,
            timeout_seconds: null,
            has_secret: false,
            api_key: null,
            last_received_at: null,
            last_status: null,
          };
          state.connections = [created];
          panel.connection_id = created.id;
        }
        if (update.connection_id) {
          panel.connection_id = update.connection_id;
        }
        panel.mode = update.mode;
        if (update.mode === "fake") {
          panel.connection_id = null;
        }
        return json(settingsFor(key as "system-health" | "logs"));
      }
      if (url === "/api/projects/harbor/connections/7/api-key" && method === "POST") {
        const key = { prefix: "a1_harborKey", created_at: "2026-10-10T12:00:00+00:00" };
        state.connections = state.connections.map((item) => (item.id === 7 ? { ...item, api_key: key } : item));
        return json({ key: "a1_harborKeySECRET", prefix: key.prefix, created_at: key.created_at }, 201);
      }
      if (url === "/api/projects/harbor/panels/system-health/test-connection" && method === "POST") {
        state.health.last_status = "up";
        state.health.last_received_at = "2026-10-10T12:05:00+00:00";
        return json({
          ok: true,
          detail: "Push is ready. This panel reads the local snapshot after data arrives.",
          last_received_at: "2026-10-10T12:05:00+00:00",
          last_status: "up",
        });
      }
      throw new Error(`unexpected fetch ${method} ${url}`);
    }),
  );
  return calls;
}

describe("panel settings", () => {
  it("keeps data source configuration on the settings route", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("admin1.token", "test-token");
    const calls = installFetch();

    render(
      <MemoryRouter initialEntries={["/projects/harbor"]}>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Harbor" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Data source")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Coming soon" })).toBeInTheDocument();

    await user.click(screen.getByRole("link", { name: "System health settings" }));
    expect(await screen.findByRole("heading", { name: "System health settings" })).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "HTTP health" })).toBeInTheDocument();
    const source = screen.getByLabelText("Data source");
    expect(source).toHaveValue("fake");
    expect(screen.queryByText(/a1_harborKeySECRET/)).not.toBeInTheDocument();

    await user.selectOptions(source, "push");
    await user.type(screen.getByLabelText("Connection name"), "Harbor app");
    await user.click(screen.getByRole("button", { name: "Save data source" }));
    expect(calls.some((call) => call.method === "PUT" && call.body && (call.body as { mode: string }).mode === "push")).toBe(
      true,
    );

    await user.click(await screen.findByRole("button", { name: "Generate API key" }));
    expect(await screen.findByText(/Copy this key. It is shown once: a1_harborKeySECRET/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Test connection" }));
    expect(await screen.findByText(/Push is ready/)).toBeInTheDocument();
    expect(screen.getByText("Last received 2026-10-10T12:05:00+00:00")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Latest status" })).toBeInTheDocument();
    expect(screen.getByText("up")).toBeInTheDocument();
  });

  it("does not offer HTTP health on a panel that cannot use it", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("admin1.token", "test-token");
    installFetch();

    render(
      <MemoryRouter initialEntries={["/projects/harbor"]}>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole("link", { name: "Logs settings" }));
    const source = await screen.findByLabelText("Data source");
    await waitFor(() => {
      expect(screen.queryByRole("option", { name: "HTTP health" })).not.toBeInTheDocument();
    });
    expect(source).toHaveValue("fake");
    expect(screen.getByRole("option", { name: "Push" })).toBeInTheDocument();
  });
});
