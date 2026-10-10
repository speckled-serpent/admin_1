import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { AuthProvider } from "../auth";

const sources: {
  api_key: { prefix: string; created_at: string } | null;
  panels: Array<{
    panel_key: string;
    mode: string;
    allowed_modes: string[];
    url: string | null;
    expected_status: number | null;
    timeout_seconds: number | null;
    has_secret: boolean;
    last_received_at: string | null;
    last_status: string | null;
  }>;
} = {
  api_key: null,
  panels: [
    {
      panel_key: "system-health",
      mode: "fake",
      allowed_modes: ["fake", "push", "http-health"],
      url: null,
      expected_status: null,
      timeout_seconds: null,
      has_secret: false,
      last_received_at: null,
      last_status: null,
    },
    {
      panel_key: "logs",
      mode: "fake",
      allowed_modes: ["fake", "push"],
      url: null,
      expected_status: null,
      timeout_seconds: null,
      has_secret: false,
      last_received_at: null,
      last_status: null,
    },
  ],
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
  sources.api_key = null;
  sources.panels[0].mode = "fake";
  sources.panels[0].last_status = null;
  sources.panels[0].last_received_at = null;
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
        return json([
          { slug: "harbor", name: "Harbor", panels: ["system-health", "logs"] },
        ]);
      }
      if (url === "/api/projects/harbor/data-sources") {
        return json(sources);
      }
      if (url === "/api/projects/harbor/panels/system-health/data-source" && method === "PUT") {
        sources.panels[0].mode = body.mode;
        return json({ ...sources.panels[0], mode: body.mode });
      }
      if (url === "/api/projects/harbor/api-key" && method === "POST") {
        sources.api_key = { prefix: "a1_harborKey", created_at: "2026-10-10T12:00:00+00:00" };
        return json({ key: "a1_harborKeySECRET", prefix: "a1_harborKey", created_at: sources.api_key.created_at }, 201);
      }
      if (url === "/api/projects/harbor/panels/system-health/test-connection" && method === "POST") {
        sources.panels[0].last_status = "up";
        sources.panels[0].last_received_at = "2026-10-10T12:05:00+00:00";
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

describe("data source setting", () => {
  it("saves push, shows a generated key once, and tests the connection", async () => {
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

    expect(await screen.findByRole("option", { name: "HTTP health" })).toBeInTheDocument();
    const source = screen.getByLabelText("Data source");
    expect(source).toHaveValue("fake");
    expect(screen.queryByText(/a1_harborKeySECRET/)).not.toBeInTheDocument();

    await user.selectOptions(source, "push");
    await user.click(screen.getByRole("button", { name: "Save data source" }));
    expect(calls.some((call) => call.method === "PUT" && call.body && (call.body as { mode: string }).mode === "push")).toBe(
      true,
    );

    await user.click(screen.getByRole("button", { name: "Generate API key" }));
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

    await user.click(await screen.findByRole("button", { name: "Logs" }));
    const source = await screen.findByLabelText("Data source");
    await waitFor(() => {
      expect(screen.queryByRole("option", { name: "HTTP health" })).not.toBeInTheDocument();
    });
    expect(source).toHaveValue("fake");
    expect(screen.getByRole("option", { name: "Push" })).toBeInTheDocument();
  });
});
