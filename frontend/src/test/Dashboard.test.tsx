import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { AuthProvider } from "../auth";
import type { Revenue } from "../types";

const revenue: Revenue = {
  project: { slug: "harbor", name: "Harbor" },
  currency: "usd",
  gross_amount: 15900,
  refunded_amount: 1700,
  net_amount: 14200,
  charge_count: 8,
  succeeded_count: 6,
  refunded_count: 2,
  charges: [
    {
      id: "ch_harbor_1008",
      amount: 1200,
      amount_refunded: 0,
      currency: "usd",
      status: "pending",
      refunded: false,
      created: 1791055320,
      description: "Harbor Pro — monthly",
      customer: "cus_harbor_ada",
    },
    {
      id: "ch_harbor_1007",
      amount: 2900,
      amount_refunded: 0,
      currency: "usd",
      status: "failed",
      refunded: false,
      created: 1790583360,
      description: "Harbor Pro — monthly",
      customer: "cus_harbor_cam",
    },
    {
      id: "ch_harbor_1005",
      amount: 800,
      amount_refunded: 200,
      currency: "usd",
      status: "succeeded",
      refunded: false,
      created: 1789929720,
      description: "Harbor export add-on",
      customer: "cus_harbor_bao",
    },
  ],
};

beforeEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("sales data panel", () => {
  it("shows revenue when sales data is bound", async () => {
    sessionStorage.setItem("admin1.token", "test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/auth/me") {
          return json({ username: "dev" });
        }
        if (url === "/api/projects") {
          return json([{ slug: "harbor", name: "Harbor", panels: ["sales-data"] }]);
        }
        if (url === "/api/projects/harbor/revenue") {
          return json(revenue);
        }
        if (url.endsWith("/data-sources")) {
          return json({ api_key: null, panels: [] });
        }
        throw new Error(`unexpected fetch ${url}`);
      }),
    );

    render(
      <MemoryRouter initialEntries={["/projects/harbor"]}>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Harbor" })).toBeInTheDocument();
    expect(await screen.findByRole("article", { name: "Gross" })).toHaveTextContent("$159.00");
    expect(screen.getByRole("article", { name: "Refunded" })).toHaveTextContent("$17.00");
    expect(screen.getByRole("article", { name: "Net" })).toHaveTextContent("$142.00");
    expect(screen.getByText("Harbor export add-on")).toBeInTheDocument();
    expect(screen.getByText("partial refund")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByText("dev")).toBeInTheDocument();
  });

  it("shows fixture revenue after Sales data settings are set to Fake", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("admin1.token", "test-token");
    let mode = "push";
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";
        if (url === "/api/auth/me") {
          return json({ username: "dev" });
        }
        if (url === "/api/projects") {
          return json([{ slug: "harbor", name: "Harbor", panels: ["sales-data"] }]);
        }
        if (url === "/api/projects/harbor/revenue") {
          if (mode !== "fake") {
            return json({ detail: "No revenue source is configured for this project" }, 404);
          }
          return json(revenue);
        }
        if (url === "/api/projects/harbor/panels/sales-data/settings" && method === "GET") {
          return json({
            panel_key: "sales-data",
            mode,
            connection_id: mode === "push" ? 4 : null,
            allowed_modes: ["fake", "push"],
            last_received_at: null,
            last_status: null,
            connections: [
              {
                id: 4,
                name: "Billing",
                kind: "push",
                url: null,
                expected_status: null,
                timeout_seconds: null,
                has_secret: false,
                api_key: null,
                last_received_at: null,
                last_status: null,
              },
            ],
          });
        }
        if (url === "/api/projects/harbor/panels/sales-data/settings" && method === "PUT") {
          const body = JSON.parse(String(init?.body)) as { mode: string };
          mode = body.mode;
          return json({
            panel_key: "sales-data",
            mode,
            connection_id: null,
            allowed_modes: ["fake", "push"],
            last_received_at: null,
            last_status: null,
            connections: [],
          });
        }
        throw new Error(`unexpected fetch ${method} ${url}`);
      }),
    );

    render(
      <MemoryRouter initialEntries={["/projects/harbor"]}>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Coming soon" })).toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Sales data settings" }));
    const source = await screen.findByLabelText("Data source");
    expect(source).toHaveValue("push");
    await user.selectOptions(source, "fake");
    await user.click(screen.getByRole("button", { name: "Save data source" }));
    await user.click(screen.getByRole("button", { name: "Sales data" }));

    expect(await screen.findByRole("article", { name: "Gross" })).toHaveTextContent("$159.00");
    expect(screen.getByRole("article", { name: "Net" })).toHaveTextContent("$142.00");
    expect(screen.queryByRole("heading", { name: "Coming soon" })).not.toBeInTheDocument();
  });
});

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
