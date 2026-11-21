import { act, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient } from "@tanstack/react-query";
import { createRouter, rootRouteId } from "@tanstack/react-router";
import { describe, expect, it, vi } from "vitest";

import { routeTree } from "@/routeTree.gen";
import { Route as IndexRoute } from "@/routes/index";

describe("App routing and workspace integration", () => {
  it("matches a page for / instead of falling back to not found", () => {
    const router = createRouter({ routeTree, context: { queryClient: new QueryClient() } });

    const matches = router.matchRoutes("/");

    expect(matches.at(-1)?.routeId).not.toBe(rootRouteId);
  });

  it("initializes session, toggles focus with Escape/click, and runs puzzle actions end-to-end", async () => {
    vi.useFakeTimers();
    sessionStorage.clear();
    try {
      const IndexComponent = IndexRoute.options.component!;
      render(<IndexComponent />);

      expect(screen.getByText("WINDING…")).toBeInTheDocument();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(150);
      });

      expect(sessionStorage.getItem("clocktower.session")).toMatch(/^sess-/);
      expect(screen.getByText(/Stage 1 — Wake the Tower/i)).toBeInTheDocument();
      expect(screen.getByLabelText("Focus switchboard")).toBeInTheDocument();

      fireEvent.keyDown(window, { key: "Escape" });
      expect(screen.getByLabelText("Focus field manual")).toBeInTheDocument();

      for (let i = 0; i < 4; i++) {
        fireEvent.click(screen.getByRole("button", { name: "PROBE" }));
        await act(async () => {
          await vi.advanceTimersByTimeAsync(2300);
        });
        fireEvent.click(screen.getByRole("button", { name: "Next target" }));
      }

      fireEvent.change(screen.getByLabelText("Setting lever"), { target: { value: "75" } });
      fireEvent.click(screen.getByRole("button", { name: "CALIBRATE" }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });

      fireEvent.click(screen.getByRole("button", { name: "ENGAGE" }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });

      expect(screen.getByText("STAGE LOGGED COMPLETE")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "NEXT STAGE" }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });
      expect(screen.getByText(/Stage 2 — Briefing/i)).toBeInTheDocument();

      fireEvent.click(screen.getByLabelText("Focus switchboard"));
      fireEvent.click(screen.getByRole("button", { name: "RESET" }));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });
      expect(screen.getByLabelText("Focus switchboard")).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
