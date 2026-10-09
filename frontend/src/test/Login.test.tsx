import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { AuthProvider } from "../auth";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("login", () => {
  it("stores a token and opens the dashboard shell", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/auth/login" && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              token: "test-token",
              token_type: "bearer",
              expires_at: "2026-10-16T00:00:00Z",
              username: "dev",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (url === "/api/auth/me") {
          return new Response(JSON.stringify({ username: "dev" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (url === "/api/projects") {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        throw new Error(`unexpected fetch ${url}`);
      }),
    );

    renderAt("/login");
    await user.clear(screen.getByLabelText("Username"));
    await user.type(screen.getByLabelText("Username"), "dev");
    await user.type(screen.getByLabelText("Password"), "devpass");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("No projects are seeded yet.")).toBeInTheDocument();
    expect(sessionStorage.getItem("admin1.token")).toBe("test-token");
  });

  it("shows the API error when the password is wrong", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Invalid username or password" }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          }),
      ),
    );

    renderAt("/login");
    await user.type(screen.getByLabelText("Password"), "nope");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid username or password");
    expect(sessionStorage.getItem("admin1.token")).toBeNull();
  });

  it("sends an anonymous visitor to the login page", () => {
    renderAt("/");
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });
});
