import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { AuthProvider } from "../auth";
import type { Revenue } from "../types";

const revenue: Revenue = {
  project: { slug: "acme-notes", name: "Acme Notes" },
  currency: "usd",
  gross_amount: 15900,
  refunded_amount: 1700,
  net_amount: 14200,
  charge_count: 8,
  succeeded_count: 6,
  refunded_count: 2,
  charges: [
    {
      id: "ch_acme_1008",
      amount: 1200,
      amount_refunded: 0,
      currency: "usd",
      status: "pending",
      refunded: false,
      created: 1791055320,
      description: "Acme Notes Pro — monthly",
      customer: "cus_acme_ada",
    },
    {
      id: "ch_acme_1007",
      amount: 2900,
      amount_refunded: 0,
      currency: "usd",
      status: "failed",
      refunded: false,
      created: 1790583360,
      description: "Acme Notes Pro — monthly",
      customer: "cus_acme_cam",
    },
    {
      id: "ch_acme_1005",
      amount: 800,
      amount_refunded: 200,
      currency: "usd",
      status: "succeeded",
      refunded: false,
      created: 1789929720,
      description: "Acme Notes export add-on",
      customer: "cus_acme_bao",
    },
  ],
};

beforeEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("dashboard", () => {
  it("shows the seeded project's revenue", async () => {
    sessionStorage.setItem("admin1.token", "test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url === "/api/auth/me") {
          return json({ username: "dev" });
        }
        if (url === "/api/projects") {
          return json([{ slug: "acme-notes", name: "Acme Notes" }]);
        }
        if (url === "/api/projects/acme-notes/revenue") {
          return json(revenue);
        }
        throw new Error(`unexpected fetch ${url}`);
      }),
    );

    render(
      <MemoryRouter initialEntries={["/"]}>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Acme Notes" })).toBeInTheDocument();
    expect(screen.getByRole("article", { name: "Gross" })).toHaveTextContent("$159.00");
    expect(screen.getByRole("article", { name: "Refunded" })).toHaveTextContent("$17.00");
    expect(screen.getByRole("article", { name: "Net" })).toHaveTextContent("$142.00");
    expect(screen.getByText("Acme Notes export add-on")).toBeInTheDocument();
    expect(screen.getByText("partial refund")).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
    expect(screen.getByText("dev")).toBeInTheDocument();
  });
});

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
