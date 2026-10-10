import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { AuthProvider } from "../auth";

function renderProject() {
  return render(
    <MemoryRouter initialEntries={["/projects/lumen"]}>
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

describe("delete panel", () => {
  it("keeps confirm disabled until DELETE and opens the next panel", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("admin1.token", "test-token");
    const deleted: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/auth/me") {
          return json({ username: "dev" });
        }
        if (url === "/api/projects/lumen/panels/system-health" && init?.method === "DELETE") {
          deleted.push(url);
          return new Response(null, { status: 204 });
        }
        if (url === "/api/projects") {
          return json([{ slug: "lumen", name: "Lumen", panels: ["system-health", "logs"] }]);
        }
        throw new Error(`unexpected fetch ${url}`);
      }),
    );

    renderProject();
    await user.click(await screen.findByRole("button", { name: "Delete panel" }));
    const dialog = screen.getByRole("dialog", { name: "Delete System health?" });
    const confirm = screen.getByRole("button", { name: "Delete" });
    expect(confirm).toBeDisabled();
    await user.type(screen.getByLabelText("Confirmation"), "delete");
    expect(confirm).toBeDisabled();
    await user.clear(screen.getByLabelText("Confirmation"));
    await user.type(screen.getByLabelText("Confirmation"), "DELETE{Enter}");
    expect(deleted).toEqual(["/api/projects/lumen/panels/system-health"]);
    expect(dialog).not.toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Logs" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Lumen" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "System health" })).not.toBeInTheDocument();
  });

  it("returns to the overview when the last panel is removed", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("admin1.token", "test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/auth/me") {
          return json({ username: "dev" });
        }
        if (url === "/api/projects/lumen/panels/logs" && init?.method === "DELETE") {
          return new Response(null, { status: 204 });
        }
        if (url === "/api/projects") {
          return json([{ slug: "lumen", name: "Lumen", panels: ["logs"] }]);
        }
        throw new Error(`unexpected fetch ${url}`);
      }),
    );

    renderProject();
    await user.click(await screen.findByRole("button", { name: "Delete panel" }));
    await user.type(screen.getByLabelText("Confirmation"), "DELETE{Enter}");
    expect(await screen.findByRole("heading", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Lumen" })).toBeInTheDocument();
  });

  it("closes on Escape without deleting", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("admin1.token", "test-token");
    const deleted: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/auth/me") {
          return json({ username: "dev" });
        }
        if (init?.method === "DELETE") {
          deleted.push(url);
          return new Response(null, { status: 204 });
        }
        if (url === "/api/projects") {
          return json([{ slug: "lumen", name: "Lumen", panels: ["logs"] }]);
        }
        throw new Error(`unexpected fetch ${url}`);
      }),
    );

    renderProject();
    await user.click(await screen.findByRole("button", { name: "Delete panel" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(deleted).toEqual([]);
    expect(screen.getByRole("button", { name: "Logs" })).toBeInTheDocument();
  });
});
