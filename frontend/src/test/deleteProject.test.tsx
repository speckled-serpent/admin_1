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

describe("delete project", () => {
  it("keeps confirm disabled until DELETE and submits on Enter", async () => {
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
        if (url === "/api/projects" && init?.method === "DELETE") {
          throw new Error("list should not be deleted");
        }
        if (url === "/api/projects/lumen" && init?.method === "DELETE") {
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
    await user.click(await screen.findByRole("button", { name: "Delete project" }));

    const dialog = screen.getByRole("dialog", { name: "Delete Lumen?" });
    const confirm = screen.getByRole("button", { name: "Delete" });
    expect(confirm).toBeDisabled();

    await user.type(screen.getByLabelText("Confirmation"), "delete");
    expect(confirm).toBeDisabled();
    expect(deleted).toEqual([]);

    await user.clear(screen.getByLabelText("Confirmation"));
    await user.type(screen.getByLabelText("Confirmation"), "DELET");
    expect(confirm).toBeDisabled();

    await user.type(screen.getByLabelText("Confirmation"), "E{Enter}");
    expect(await screen.findByRole("heading", { name: "No projects started yet. Create one" })).toBeInTheDocument();
    expect(deleted).toEqual(["/api/projects/lumen"]);
    expect(screen.queryByRole("link", { name: "Lumen" })).not.toBeInTheDocument();
    expect(dialog).not.toBeInTheDocument();
  });

  it("closes on cancel without deleting", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("admin1.token", "test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/auth/me") {
          return json({ username: "dev" });
        }
        if (init?.method === "DELETE") {
          throw new Error("delete should not be called");
        }
        if (url === "/api/projects") {
          return json([{ slug: "lumen", name: "Lumen", panels: ["logs"] }]);
        }
        throw new Error(`unexpected fetch ${url}`);
      }),
    );

    renderProject();
    await user.click(await screen.findByRole("button", { name: "Delete project" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Lumen" })).toBeInTheDocument();
  });

  it("closes on Escape without deleting", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("admin1.token", "test-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/auth/me") {
          return json({ username: "dev" });
        }
        if (init?.method === "DELETE") {
          throw new Error("delete should not be called");
        }
        if (url === "/api/projects") {
          return json([{ slug: "lumen", name: "Lumen", panels: ["logs"] }]);
        }
        throw new Error(`unexpected fetch ${url}`);
      }),
    );

    renderProject();
    await user.click(await screen.findByRole("button", { name: "Delete project" }));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Lumen" })).toBeInTheDocument();
  });
});
